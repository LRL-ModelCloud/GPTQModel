import copy
import logging
import os.path
from typing import Dict, List, Sequence, Union

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset


IGNORE_ID = -100

# prepare calibration samples
class CalibrationDataset(Dataset):
    """
    Dataset class for calibration. Initialize with the loaded Ovis model, and a sample list in the following format:
    data_list = [
        {
            "image": "path/to/image/of/this/sample",
            "conversations": [
                {
                    "from": "human",
                    "value": "<image>\n[Your sample prompt]"
                },
                {
                    "from": "gpt",
                    "value": "[Anything]"
                }
            ]
        },
        ...
    ]
    """

    def __init__(self, model, text_max_length, data_list: List[Dict]):
        self.data = data_list
        self.model = model
        self.visual_tokenizer = model.get_visual_tokenizer()
        self.text_max_length = text_max_length

    def __len__(self):
        return len(self.data)

    def __getitem__(self, i: int) -> Dict[str, torch.Tensor]:
        sample = self.data[i]
        conversations = copy.deepcopy(sample["conversations"])
        images = [Image.open(os.path.join(self.model.model_id_or_path, f"images/{sample['id']}"))]
        max_partition = 9

        prompt, input_ids, pixel_values, labels = self.model.preprocess_inputs(
            conversations,
            images,
            max_partition=max_partition,
            generation_preface=None,
            return_labels=True,
            propagate_exception=False
        )

        if pixel_values is None:
            pixel_values, _ = self.visual_tokenizer.mock_input()

        input_ids = input_ids[:self.text_max_length]
        labels = labels[:self.text_max_length]

        return {
            "pixel_values": pixel_values,
            "input_ids": input_ids,
            "labels": labels
        }


class DataCollatorForMultimodalDatasetGPTQ:
    def __init__(self, text_tokenizer):
        self.text_tokenizer = text_tokenizer

    def __call__(self, instances: Sequence[Dict]) -> Dict[str, Union[torch.Tensor, List[torch.Tensor]]]:
        pixel_values, input_ids, labels = tuple([instance[key] for instance in instances]
                                                for key in ("pixel_values", "input_ids", "labels"))
        input_ids = torch.nn.utils.rnn.pad_sequence(
            input_ids,
            batch_first=True,
            padding_value=self.text_tokenizer.pad_token_id)
        attention_mask = torch.ne(input_ids, self.text_tokenizer.pad_token_id)
        labels = torch.nn.utils.rnn.pad_sequence(
            labels,
            batch_first=True,
            padding_value=IGNORE_ID)

        num_valid_label = torch.not_equal(labels, IGNORE_ID).sum().item()
        if num_valid_label == 0:
            logging.warning(
                f'[DataCollatorForMultimodalDatasetGPTQ] All labels are ignored, may causing training instability\n{input_ids=}\n{attention_mask=}\n{labels=}')
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
            "pixel_values": pixel_values
        }


class MyDataLoader(DataLoader):
    def __len__(self):
        return len(self.dataset) // self.batch_size  # must set drop last=True


# prepare your own calibration samples here
data_list = [{"id": "10593.jpg", "image": ["10593.jpg"], "conversations": [{"from": "human", "value": "<image>\nWrite a detailed description of this image, do not forget about the texts on it if they exist. Also, do not forget to mention the type / style of the image. No bullet points. When writing descriptions, prioritize clarity and direct observation over embellishment or interpretation.\nDon't forget these rules:\n1. **Be Direct and Concise**: Provide straightforward descriptions without adding interpretative or speculative elements.\n2. **Use Segmented Details**: Break down details about different elements of an image into distinct sentences, focusing on one aspect at a time.\n3. **Maintain a Descriptive Focus**: Prioritize purely visible elements of the image, avoiding conclusions or inferences.\n4. **Follow a Logical Structure**: Begin with the central figure or subject and expand outward, detailing its appearance before addressing the surrounding setting.\n5. **Avoid Juxtaposition**: Do not use comparison or contrast language; keep the description purely factual.\n6. **Incorporate Specificity**: Mention age, gender, race, and specific brands or notable features when present, and clearly identify the medium if it's discernible."}, {"from": "gpt", "value": "A digital rendering shows two sleek, metal cabinet handles against a white background. Each handle is cylindrical with a matte silver finish and mounts using two cylindrical pegs, visualizing a minimalistic and modern design suitable for kitchen or furniture cabinetry."}], "url": "https://www.shopgoldenwarm.com/cdn/shop/products/SKU-24-1003-3_4inholecenters_700x700.jpg?v=1691814633"}, {"id": "8383.jpg", "image": ["8383.jpg"], "conversations": [{"from": "human", "value": "Write a detailed description of this image, do not forget about the texts on it if they exist. Also, do not forget to mention the type / style of the image. No bullet points. When writing descriptions, prioritize clarity and direct observation over embellishment or interpretation.\nDon't forget these rules:\n1. **Be Direct and Concise**: Provide straightforward descriptions without adding interpretative or speculative elements.\n2. **Use Segmented Details**: Break down details about different elements of an image into distinct sentences, focusing on one aspect at a time.\n3. **Maintain a Descriptive Focus**: Prioritize purely visible elements of the image, avoiding conclusions or inferences.\n4. **Follow a Logical Structure**: Begin with the central figure or subject and expand outward, detailing its appearance before addressing the surrounding setting.\n5. **Avoid Juxtaposition**: Do not use comparison or contrast language; keep the description purely factual.\n6. **Incorporate Specificity**: Mention age, gender, race, and specific brands or notable features when present, and clearly identify the medium if it's discernible.<image>\n"}, {"from": "gpt", "value": "The image displays a screenshot of a Wikipedia page in French. The title of the article is \"Attention,\" which is prominently displayed at the top of the page. Below the title is the Wikipedia logo and a series of links such as \"Article,\" \"Discussion,\" \"Lire,\" \"Modifier,\" \"Modifier le code,\" \"Historique,\" and more, typical of Wikipedia's interface.\n\nThe main body of the screenshot shows a paragraph of text in French, beginning with a definition of attention as the faculty of focusing the mind on an object. The text explains various aspects of attention, mentioning philosophers, psychologists, and neuroscientists.\n\nTo the right of the paragraph, there is a small image within the Wikipedia page. It features three people sitting on a bench. The person on the left is wearing a green top, the one in the middle is in a red top, and the one on the right is in a blue top. They appear to be waiting or resting, with the central figure looking towards the camera.\n\nBelow the initial paragraph, there is a bullet-point list, which seems to continue the discussion on attention, possibly enumerating different points or aspects related to the topic.\n\nThe Wikipedia interface elements, such as tabs and side navigation options, are visible on the left side of the screenshot, indicating options like \"Accueil,\" \"Portails thématiques,\" \"Contact,\" \"Contribuer,\" and others."}], "url": "http://cdn.pearltrees.com/s/preview/index?urlId=236938"}, {"id": "6660.jpg", "image": ["6660.jpg"], "conversations": [{"from": "human", "value": "Write a detailed description of this image, do not forget about the texts on it if they exist. Also, do not forget to mention the type / style of the image. No bullet points. When writing descriptions, prioritize clarity and direct observation over embellishment or interpretation.\nDon't forget these rules:\n1. **Be Direct and Concise**: Provide straightforward descriptions without adding interpretative or speculative elements.\n2. **Use Segmented Details**: Break down details about different elements of an image into distinct sentences, focusing on one aspect at a time.\n3. **Maintain a Descriptive Focus**: Prioritize purely visible elements of the image, avoiding conclusions or inferences.\n4. **Follow a Logical Structure**: Begin with the central figure or subject and expand outward, detailing its appearance before addressing the surrounding setting.\n5. **Avoid Juxtaposition**: Do not use comparison or contrast language; keep the description purely factual.\n6. **Incorporate Specificity**: Mention age, gender, race, and specific brands or notable features when present, and clearly identify the medium if it's discernible.<image>\n"}, {"from": "gpt", "value": "The image is a photograph of an individual riding a two-wheeled electric scooter on a paved road. The rider is wearing protective gear which includes a helmet with a predominantly white, black, and orange color scheme, a black jacket with white accents, and black pants. The jacket is branded with the name \"VANUCCI\" in white letters on the sleeve. The electric scooter features a prominent front wheel with a disc brake, a smaller rear wheel also with a disc brake, and a blue foot platform with orange and white details. The scooter is equipped with a side-mounted kickstand, which is currently retracted, and a digital display screen mounted on the handlebars. The rider's shoes have orange accents that match the scooter's color scheme. The setting is a natural environment with trees and shrubs in the background, suggesting that the location could be a park or a rural area. Additionally, there is a watermark overlay on the image with the word \"PREVIEW\" in capital letters, indicating that the image is likely for review or pre-purchase purposes."}], "url": "https://mcn-images.bauersecure.com/PageFiles/670437/KTM-City-e-Scooter.jpg"}, {"id": "7977.jpg", "image": ["7977.jpg"], "conversations": [{"from": "human", "value": "<image>\nWrite a detailed description of this image, do not forget about the texts on it if they exist. Also, do not forget to mention the type / style of the image. No bullet points. When writing descriptions, prioritize clarity and direct observation over embellishment or interpretation.\nDon't forget these rules:\n1. **Be Direct and Concise**: Provide straightforward descriptions without adding interpretative or speculative elements.\n2. **Use Segmented Details**: Break down details about different elements of an image into distinct sentences, focusing on one aspect at a time.\n3. **Maintain a Descriptive Focus**: Prioritize purely visible elements of the image, avoiding conclusions or inferences.\n4. **Follow a Logical Structure**: Begin with the central figure or subject and expand outward, detailing its appearance before addressing the surrounding setting.\n5. **Avoid Juxtaposition**: Do not use comparison or contrast language; keep the description purely factual.\n6. **Incorporate Specificity**: Mention age, gender, race, and specific brands or notable features when present, and clearly identify the medium if it's discernible."}, {"from": "gpt", "value": "This is a promotional image for a StoryBook Legacy product by Forever, featuring \"Delight Diva 11x8.5 Pre-designed Pages\". The image is a collage-style layout that includes several photographs and graphic elements. At the top of the image, the text reads \"StoryBook Legacy™ by FOREVER\" in bold, black letters against a white background. Below that, there's a disclaimer in red text stating \"not all art shown\".\n\nThe central part of the image shows a scrapbook page layout with a pink and black color scheme. It includes three photographs: one large image of a young girl lying in grass, peeking through a hole in a pink fence, and two smaller images showing the same girl—one where she is holding a flower and smiling, and another where she is twirling in a blue dress in a grassy field. The photos are framed with decorative borders, and there are ornamental graphic elements like a circular design with concentric rings and a small graphic resembling a pink luggage tag.\n\nAt the bottom of the image, there is a text bubble in blue with white text that says \"new preview same great content.\" The overall style of the image is colorful and resembles a scrapbook or photo album page, promoting the idea of preserving memories in a creative and decorative way."}], "url": "https://d31czii1zefd9w.cloudfront.net/product_images/images/000/001/019/medium/SBL_DelightDiva11x8PDP_Preview-Med.jpg?1547494354"}, {"id": "8957.jpg", "image": ["8957.jpg"], "conversations": [{"from": "human", "value": "<image>\nWrite a detailed description of this image, do not forget about the texts on it if they exist. Also, do not forget to mention the type / style of the image. No bullet points. When writing descriptions, prioritize clarity and direct observation over embellishment or interpretation.\nDon't forget these rules:\n1. **Be Direct and Concise**: Provide straightforward descriptions without adding interpretative or speculative elements.\n2. **Use Segmented Details**: Break down details about different elements of an image into distinct sentences, focusing on one aspect at a time.\n3. **Maintain a Descriptive Focus**: Prioritize purely visible elements of the image, avoiding conclusions or inferences.\n4. **Follow a Logical Structure**: Begin with the central figure or subject and expand outward, detailing its appearance before addressing the surrounding setting.\n5. **Avoid Juxtaposition**: Do not use comparison or contrast language; keep the description purely factual.\n6. **Incorporate Specificity**: Mention age, gender, race, and specific brands or notable features when present, and clearly identify the medium if it's discernible."}, {"from": "gpt", "value": "The image is a portrait-style photograph of a man standing against a neutral background. The man appears to be in his mid to late twenties, with short brown hair and a light beard. He is looking directly at the camera, with a neutral expression on his face.\n\nHe is wearing a light gray short-sleeved t-shirt with a graphic design across the chest. The design features the word \"HILFIGER\" in capital letters. The letters are stylized with a combination of vertical stripes and a gradient that transitions from blue, white, to pink from left to right.\n\nThe man is also wearing dark blue denim jeans, although only the top part of the jeans is visible in the image. The photograph focuses on the man from the waist up, and his arms are hanging by his sides, with his hands slightly curled.\n\nThe style of the image seems to be a typical fashion or retail display meant to showcase the t-shirt design. The lighting is even and bright, enhancing the visibility of the t-shirt's graphic and the details of the man's appearance. The photograph is taken with the subject centered, emphasizing the apparel."}], "url": "https://i8.amplience.net/i/jpl/te_142563_a?qlt=80&unsharp=0,1,1,7&w=600&h=777&v=1"}, {"id": "2627.jpg", "image": ["2627.jpg"], "conversations": [{"from": "human", "value": "<image>\nWrite a detailed description of this image, do not forget about the texts on it if they exist. Also, do not forget to mention the type / style of the image. No bullet points. When writing descriptions, prioritize clarity and direct observation over embellishment or interpretation.\nDon't forget these rules:\n1. **Be Direct and Concise**: Provide straightforward descriptions without adding interpretative or speculative elements.\n2. **Use Segmented Details**: Break down details about different elements of an image into distinct sentences, focusing on one aspect at a time.\n3. **Maintain a Descriptive Focus**: Prioritize purely visible elements of the image, avoiding conclusions or inferences.\n4. **Follow a Logical Structure**: Begin with the central figure or subject and expand outward, detailing its appearance before addressing the surrounding setting.\n5. **Avoid Juxtaposition**: Do not use comparison or contrast language; keep the description purely factual.\n6. **Incorporate Specificity**: Mention age, gender, race, and specific brands or notable features when present, and clearly identify the medium if it's discernible."}, {"from": "gpt", "value": "The image is a digital presentation slide with a minimalist design. The background is split into two distinct colors: the top portion is orange, and the bottom portion is gray. Centered on the orange section in white, sans-serif font is the text \"Intermediate Strategic Management,\" which appears to be the title of the presentation. Below the title, also in white text but smaller size, is the name \"Marco Clemente.\" In the gray section, two lines of white text provide additional information: \"Spring 2014\" on the first line and \"3rd session – 5 March 2014\" on the second line, indicating the time frame of the course and the specific session date. In the upper left corner of the image, there is a stylized 'A' logo with a superscript exclamation mark, suggesting it is the logo of the institution or organization associated with the presentation, which is Aalto University School of Business. The overall style of the image is formal and academic."}], "url": "https://thumbs.slideserve.com/1_1678414.jpg"}, {"id": "9370.jpg", "image": ["9370.jpg"], "conversations": [{"from": "human", "value": "Write a detailed description of this image, do not forget about the texts on it if they exist. Also, do not forget to mention the type / style of the image. No bullet points. When writing descriptions, prioritize clarity and direct observation over embellishment or interpretation.\nDon't forget these rules:\n1. **Be Direct and Concise**: Provide straightforward descriptions without adding interpretative or speculative elements.\n2. **Use Segmented Details**: Break down details about different elements of an image into distinct sentences, focusing on one aspect at a time.\n3. **Maintain a Descriptive Focus**: Prioritize purely visible elements of the image, avoiding conclusions or inferences.\n4. **Follow a Logical Structure**: Begin with the central figure or subject and expand outward, detailing its appearance before addressing the surrounding setting.\n5. **Avoid Juxtaposition**: Do not use comparison or contrast language; keep the description purely factual.\n6. **Incorporate Specificity**: Mention age, gender, race, and specific brands or notable features when present, and clearly identify the medium if it's discernible.<image>\n"}, {"from": "gpt", "value": "The image depicts a red wax seal with embossed text. The text within the seal reads \"DUTY\" in large, bold letters at the center, and a border text that is partially obscured, includes the words \"QUALITY\" and \"SERVICE.\" The seal has a circular shape with scalloped edges, which is typical of traditional wax seals, and it has a glossy texture that reflects light, suggesting a three-dimensional appearance. The background is white, which contrasts with the red color of the seal, making the seal the focal point of the image. The style of the image is graphic and appears to be digitally created rather than an actual photograph of a physical wax seal."}], "url": "https://static0.bigstockphoto.com/thumbs/7/8/5/small2/5871191.jpg"}, {"id": "558.jpg", "image": ["558.jpg"], "conversations": [{"from": "human", "value": "<image>\nWrite a detailed description of this image, do not forget about the texts on it if they exist. Also, do not forget to mention the type / style of the image. No bullet points. When writing descriptions, prioritize clarity and direct observation over embellishment or interpretation.\nDon't forget these rules:\n1. **Be Direct and Concise**: Provide straightforward descriptions without adding interpretative or speculative elements.\n2. **Use Segmented Details**: Break down details about different elements of an image into distinct sentences, focusing on one aspect at a time.\n3. **Maintain a Descriptive Focus**: Prioritize purely visible elements of the image, avoiding conclusions or inferences.\n4. **Follow a Logical Structure**: Begin with the central figure or subject and expand outward, detailing its appearance before addressing the surrounding setting.\n5. **Avoid Juxtaposition**: Do not use comparison or contrast language; keep the description purely factual.\n6. **Incorporate Specificity**: Mention age, gender, race, and specific brands or notable features when present, and clearly identify the medium if it's discernible."}, {"from": "gpt", "value": "The image depicts an interior view of a warehouse. The flooring is a smooth concrete surface that extends throughout the space. On the left, there are tall orange and blue industrial shelving units filled with various materials and boxes, suggesting a storage function. A yellow pallet jack stands in front of the shelves, positioned perpendicular to them.\n\nIn the middle of the warehouse, there is a large, yellow overhead crane system with a hook, which spans across the width of the space. Below the crane, there are stacks of construction materials, such as boards and panels, neatly arranged on the floor. These materials appear to be ready for transport or storage.\n\nThe warehouse has a high ceiling with multiple skylights and artificial lighting fixtures that illuminate the space evenly. To the right, there is a semi-opened roller shutter door, providing access to the outside and allowing natural light to enter. There are no visible texts or distinctive brands in the image. The style of the photograph is professional, with a focus on capturing the layout and equipment of the warehouse environment for either inventory management or real estate presentation purposes."}], "url": "https://img.agentaccount.com/5d8aee01cb7cd06e6f366e134e11494b8ee1ea47"}, {"id": "11323.jpg", "image": ["11323.jpg"], "conversations": [{"from": "human", "value": "<image>\nWrite a detailed description of this image, do not forget about the texts on it if they exist. Also, do not forget to mention the type / style of the image. No bullet points. When writing descriptions, prioritize clarity and direct observation over embellishment or interpretation.\nDon't forget these rules:\n1. **Be Direct and Concise**: Provide straightforward descriptions without adding interpretative or speculative elements.\n2. **Use Segmented Details**: Break down details about different elements of an image into distinct sentences, focusing on one aspect at a time.\n3. **Maintain a Descriptive Focus**: Prioritize purely visible elements of the image, avoiding conclusions or inferences.\n4. **Follow a Logical Structure**: Begin with the central figure or subject and expand outward, detailing its appearance before addressing the surrounding setting.\n5. **Avoid Juxtaposition**: Do not use comparison or contrast language; keep the description purely factual.\n6. **Incorporate Specificity**: Mention age, gender, race, and specific brands or notable features when present, and clearly identify the medium if it's discernible."}, {"from": "gpt", "value": "The image is a photograph that displays a segment of an object divided into two colored sections: purple on the left and green on the right. On the purple section, there is a circular port or interface with multiple pin slots arranged in a pattern. Above this port, a small rectangular keyboard icon is affixed. On the green section, another circular port or interface is present, with a different configuration of pin slots. Just above this port on the green section, there is an icon depicting a mouse. The background beyond the two sections is black, creating a contrast with the vibrant colors of the object. The ports resemble PS/2 ports, commonly used for keyboards and mice in older computers."}], "url": "https://i.imgur.com/skIxCXJ.jpg"}]
target_length = 16
data_list = (data_list * (target_length // len(data_list) + 1))[:target_length]


def get_calib_dataset(model):
    train_dataset = CalibrationDataset(model, text_max_length=832, data_list=data_list)
    print("Dataset Loaded!")
    print(f"Total length of the training set: {len(train_dataset)}")

    train_loader = MyDataLoader(
        train_dataset,
        collate_fn=DataCollatorForMultimodalDatasetGPTQ(model.get_text_tokenizer()),
        shuffle=False,
        batch_size=1,
        drop_last=True,
        pin_memory=True,
    )
    print("Dataloader Loaded!")
    return train_loader

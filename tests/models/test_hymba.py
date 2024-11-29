from gptqmodel import GPTQModel
from model_test import ModelTest


class TestHymba(ModelTest):
    NATIVE_MODEL_ID = "/monster/data/model/Hymba-1.5B-Instruct/"  # "baichuan-inc/Baichuan2-7B-Chat"
    NATIVE_ARC_CHALLENGE_ACC = 0.2073
    NATIVE_ARC_CHALLENGE_ACC_NORM = 0.2713
    MODEL_MAX_LEN = 8192
    TRUST_REMOTE_CODE = True
    APPLY_CHAT_TEMPLATE = True
    # Hymba currently only supports a batch size of 1.
    # See https://huggingface.co/nvidia/Hymba-1.5B-Instruct
    BATCH_SIZE = 1

    def test_hymba(self):
        self.quant_lm_eval()
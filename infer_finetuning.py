# -*- coding: utf-8 -*-
# @Time    : 2023/3/9 15:29
import os
import re
from collections import OrderedDict

import torch
from deep_training.data_helper import ModelArguments, TrainingArguments, DataArguments
from transformers import HfArgumentParser

from data_utils import train_info_args, NN_DataHelper, get_deepspeed_config
from models import MyTransformer,MossTokenizer,MossConfig,LoraArguments,PromptArguments

deep_config = get_deepspeed_config()


if __name__ == '__main__':
    train_info_args['seed'] = None
    train_info_args['model_name_or_path'] = None

    parser = HfArgumentParser((ModelArguments, TrainingArguments, DataArguments, LoraArguments,PromptArguments))
    model_args, training_args, data_args, _,_ = parser.parse_dict(train_info_args)

    

    dataHelper = NN_DataHelper(model_args, training_args, data_args)
    tokenizer: MossTokenizer
    tokenizer, _, _, _ = dataHelper.load_tokenizer_and_config(tokenizer_class_name=MossTokenizer, config_class_name=MossConfig,config_kwargs={"torch_dtype": "float16"})
    ###################### 注意 选最新权重
    #选择最新的权重 ， 根据时间排序 选最新的
    config = MossConfig.from_pretrained('./best_ckpt')
    config.initializer_weight = False


    if deep_config is None:
        train_weight = './best_ckpt/last-v3.ckpt'
        assert os.path.exists(train_weight)
        pl_model = MyTransformer.load_from_checkpoint(train_weight, config=config,model_args=model_args,
                                                   training_args=training_args,strict=False)
    else:

        #建议直接使用转换脚本命令 支持 deepspeed stage 0,1,2,3， 生成 ./best_ckpt/last.ckpt/best.pt 权重文件
        # cd best_ckpt/last.ckpt
        # python zero_to_fp32.py . best.pt
        train_weight = './best_ckpt/last.ckpt/best.pt'

        #deepspeed stage 0,1,2 不必须执行上面命令
        #train_weight = './best_ckpt/last.ckpt/checkpoint/mp_rank_00_model_states.pt'

        assert os.path.exists(train_weight)
        weights_dict = torch.load(train_weight)
        weights_dict_new = OrderedDict()
        for k,v in (weights_dict['module'] if 'module' in weights_dict else weights_dict).items():
            weights_dict_new[re.sub(r'_forward_module\.', '', k)] = v
        pl_model = MyTransformer(config=config, model_args=model_args, training_args=training_args)
        pl_model.load_state_dict(state_dict= weights_dict_new, strict=False)

    model = pl_model.get_llm_model()
    model.half().cuda()
    model = model.eval()

    query = "<|Human|>: 你好<eoh>\n<|MOSS|>:"
    response = model.chat(tokenizer, query,  max_length=2048,
                          eos_token_id=config.eos_token_id,
                          do_sample=True, top_p=0.7, temperature=0.95,
                          )
    print(query, ' 返回: ', response)

    query = response + "\n<|Human|>: 推荐五部科幻电影<eoh>\n<|MOSS|>:"
    response = model.chat(tokenizer, query, max_length=2048,
                          eos_token_id=config.eos_token_id,
                          do_sample=True, top_p=0.7, temperature=0.95,
                          )
    print(query, ' 返回: ', response)


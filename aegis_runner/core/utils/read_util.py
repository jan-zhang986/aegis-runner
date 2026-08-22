#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author : Jan
import yaml



class YamlUtil:
    __instance = None

    def __new__(cls, *args, **kwargs):
        if not cls.__instance:

            cls.__instance = super(YamlUtil, cls).__new__(cls, *args, **kwargs)
        return cls.__instance


    def read_yaml(self, path) ->dict:
        try:
            with open(path, encoding="utf-8") as f:
                result = f.read()
                result = yaml.load(result, Loader=yaml.FullLoader)
                return result
        except Exception as e:
            pass

    @classmethod
    def read_config_yaml(cls, path) -> dict:
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
                data = yaml.load(raw, Loader=yaml.FullLoader)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}








yml = YamlUtil()

if __name__ == '__main__':
   pass
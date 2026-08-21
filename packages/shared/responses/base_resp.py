# -*- coding: utf-8 -*-
"""
@author Jan
@date 2023-04-03
@packageName 
@className response
"""

from fastapi import status
from fastapi.responses import JSONResponse, Response
from typing import Union, Optional, Text, Any, Dict, List

from pydantic import BaseModel

# 历史接口 success_response_200 使用；无业务常量模块依赖
_APP_HEADER = "aegis-runner"


class BaseRespModel(BaseModel):
    # resp: Dict
    code: int
    message: str
    data: Union[Any] = None







def resp_200(*, data: Union[Any]) -> Response:
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            'code': 200,
            'message': "Success",
            'data': data,
        }
    )


def resp_500(*, message: str = "") -> Response:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            'code': 500,
            'message': message,
            'data': None,
        }
    )


def resp_400(*, data: Optional[str] = None, message: str = "BAD REQUEST") -> Response:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            'code': 400,
            'message': message,
            'data': data,
        }
    )

def success_response_200(*, token, data: Optional[Any] = None, message: str = "success") -> Response:
    response = JSONResponse(
        status_code=status.HTTP_200_OK,

        content={
            'code': 200,
            'message': message,
            'data': data,
        }
    )
    response.headers['Authorization'] = token
    response.headers['Set-Cookie'] = token
    response.headers['Cookie'] = token
    response.headers['x-app'] = _APP_HEADER
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


def success_response(data: Optional[Any] = None, message: str = "success") -> BaseRespModel:
    return BaseRespModel(code=200, message=message, data=data)


def error_response(code: int, message: str,data:Optional[Any]=None) -> BaseRespModel:
    return BaseRespModel(code=code, data=data,message=message)




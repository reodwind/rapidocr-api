# -*- encoding: utf-8 -*-
# @Author: SWHL
# @Contact: liekkaskono@163.com
import argparse
import base64
import importlib.util
import io
import os
import re
import sys
import logging
import json
from pathlib import Path
from typing import Dict, Self

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, Form, UploadFile
from PIL import Image

if importlib.util.find_spec("rapidocr"):
    from rapidocr import RapidOCR
else:
    raise ImportError(
        "Please install one of [rapidocr_onnxruntime,rapidocr-paddle,rapidocr-openvino]"
    )

sys.path.append(str(Path(__file__).resolve().parent.parent))

log = logging.getLogger("uvicorn")


class OCRAPIUtils:
    def __init__(self) -> None:
        config_path = os.getenv("CONFIG_PATH", None)

        if config_path is None:
            self.ocr = RapidOCR(config_path="./config.yaml")
        else:
            self.ocr = RapidOCR(config_path=config_path)

    def __call__(
        self,
        img: Image.Image,
        use_det=None,
        use_cls=None,
        use_rec=None,
        return_word_box=None,
        **kwargs,
    ) -> Self:
        img = np.array(img)
        self.ocr_res = self.ocr(
            img,
            use_det=use_det,
            use_cls=use_cls,
            use_rec=use_rec,
            return_word_box=return_word_box,
            **kwargs,
        )

        if not self.ocr_res:
            return self

        self.img_np = self.ocr_res.vis()
        return self

    def ocr_to_txt(self):
        if not self.ocr_res or not self.ocr_res.txts:
            return ""
        return "".join(self.ocr_res.txts)

    def ocr_to_json(self) -> Dict:
        out_dict = {}
        if self.ocr_res:
            values = {}
            match type(self.ocr_res).__name__:
                case "RapidOCROutput" | "TextRecOutput":
                    log.debug("RapidOCROutput or TextRecOutput")
                    out_dict["txt"] = "".join(self.ocr_res.txts)
                    values = {
                        "txts": json.loads(json.dumps(self.ocr_res.txts)),
                        "boxes": json.dumps(self.ocr_res.boxes.tolist()),
                        "scores": json.loads(json.dumps(self.ocr_res.scores)),
                        "word_results ": json.loads(
                            json.dumps(self.ocr_res.word_results)
                        ),
                        "elapse": self.ocr_res.elapse,
                    }
                case "TextDetOutput":
                    log.debug("TextDetOutput")
                    values = {
                        "boxes": self.ocr_res.boxes,
                        "scores": json.loads(json.dumps(self.ocr_res.scores)),
                        "elapse": self.ocr_res.elapse,
                    }
                case "TextClsOutput":
                    log.debug("TextClsOutput")
                    values = {
                        "cls_res": json.loads(json.dumps(self.ocr_res.cls_res)),
                        "elapse": self.ocr_res.elapse,
                    }
                case _:
                    log.warning("ocr_res type unknown")
            out_dict["result"] = values
            out_dict["image_base64"] = self.numpy_to_base64()
        return out_dict

    def numpy_to_base64(self):
        _, buffer = cv2.imencode(".png", self.img_np)
        image_bytes = buffer.tobytes()
        image_base4 = base64.b64encode(image_bytes).decode("utf8")
        return image_base4


app = FastAPI()
processor = OCRAPIUtils()


@app.get("/")
def root():
    return {"message": "Welcome to RapidOCR API Server!"}


@app.post("/ocr")
def ocr(
    image_file: UploadFile = None,
    image_data: str = Form(None),
    use_det: bool = Form(None),
    use_cls: bool = Form(None),
    use_rec: bool = Form(None),
    word_box: bool = Form(None),
):
    if image_file:
        img = Image.open(image_file.file)
    elif image_data:
        img_bytes = str.encode(image_data)
        img_b64decode = base64.b64decode(img_bytes)
        img = Image.open(io.BytesIO(img_b64decode))
    else:
        raise ValueError(
            "When sending a post request, data or files must have a value."
        )
    ocr_res = processor(
        img, use_det=use_det, use_cls=use_cls, use_rec=use_rec, return_word_box=word_box
    )
    return ocr_res.ocr_to_json()


@app.post("/captcha/base64")
@app.post("/captcha")
async def captcha_base64(
    image_file: UploadFile = None,
    image_data: str = Form(None),
    base64_img: str = Form(None),
    use_det: bool = Form(None),
    use_cls: bool = Form(None),
    use_rec: bool = Form(None),
    word_box: bool = Form(None),
):
    if image_file:
        img = Image.open(image_file.file)
    elif image_data:
        img_bytes = str.encode(image_data)
        img_b64decode = base64.b64decode(img_bytes)
        img = Image.open(io.BytesIO(img_b64decode))
    elif base64_img:
        img_bytes = str.encode(base64_img)
        img_b64decode = base64.b64decode(img_bytes)
        img = Image.open(io.BytesIO(img_b64decode))
    else:
        raise ValueError(
            "When sending a post request, data or files must have a value."
        )
    ocr_res = processor(
        img, use_cls=use_cls, use_det=use_det, use_rec=use_rec, return_word_box=word_box
    )
    result = "".join(re.findall(r"[A-Za-z0-9]", ocr_res.ocr_to_txt()))
    return {"result": result}


def main():
    parser = argparse.ArgumentParser("api")
    parser.add_argument("-ip", "--ip", type=str, default="0.0.0.0", help="IP Address")
    parser.add_argument("-p", "--port", type=int, default=80, help="IP port")
    parser.add_argument(
        "-workers", "--workers", type=int, default=1, help="number of worker process"
    )
    args = parser.parse_args()

    # 修改 uvicorn 的默认日志配置
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = "%(asctime)s %(levelname)s %(message)s"
    log_config["formatters"]["default"]["fmt"] = "%(asctime)s %(levelname)s %(message)s"

    uvicorn.run(
        "api:app",
        host=args.ip,
        port=args.port,
        reload=0,
        workers=args.workers,
        log_config=log_config,
    )


if __name__ == "__main__":
    main()

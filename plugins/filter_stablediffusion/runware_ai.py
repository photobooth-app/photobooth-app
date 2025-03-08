import base64
import json
import io
from io import BytesIO
from re import sub
import logging
import requests
from PIL import Image

logger = logging.getLogger(__name__)

class RunwareAIFilter:
    def __init__(self, filter: str) -> None:
        self.filter = filter

    def __call__(self, params, image: Image.Image) -> Image.Image:
        try:
            
            buffered = BytesIO()
            size = 1024, 1024
            image.thumbnail(size, Image.Resampling.LANCZOS)
            image.save(buffered, format="JPEG")

            img_str = base64.b64encode(buffered.getvalue())
            img_str = img_str.decode("ascii")
            session = requests.Session()
            url = "https://api.runware.ai/v1"
            apiKey = ""
            headers = { "Authorization": "Bearer " + apiKey }
            import uuid

            taskuuid = str( uuid.uuid4() )

            imageUploadPayload =  [{
                "taskType": "imageUpload",
                "taskUUID": taskuuid,
                "image": img_str
            }]
            response = session.post(url=url, json=imageUploadPayload, headers=headers)
            if response.ok :
                r = json.loads( response.text )
            else:
                logger.debug( "Imageupload request to runware.ai failed: " + repr ( response ))
                raise RuntimeError("Imageupload request to runware.ai failed")
            data = r["data"];
            #print( repr( data ))
            imageUUID = data[0]["imageUUID"]
            # fluxPayload =  [
            #     {
            #         "taskType": "imageInference",
            #         "taskUUID": str(uuid.uuid4()),
            #         "model": "runware:101@1",
            #         "positivePrompt": params["prompt"],
            #         "width": 768,
            #         "height": 512,
            #         "steps": 30,
            #         "strength": 0.35,
            #         "outputType": "base64Data",
            #         #"ipAdapter": [
            #         # {
            #         #    "guideImage": imageUUID,
            #         #    "model": "runware:105@1"
            #         # }
            #         # ]
            #         "controlNet": [
            #         {
            #             "model": "runware:27@1",
            #             "guideImage": imageUUID,
            #             "startStep": 1,
            #             "endStep": 15,
            #             "weight": 1
            #         }
            #         ]
            #     }
            #     ]
            # fluxPayload =  [
            #     {
            #         "taskType": "imageInference",
            #         "taskUUID": str(uuid.uuid4()),
            #         "model": "runware:101@1",
            #         "positivePrompt": params["prompt"],
            #         "width": params["width"],
            #         "height": params["height"],
            #         "outputType": "base64Data",
            #         "steps": 30,
            #         "ipAdapter": [
            #         {
            #             "guideImage": imageUUID,
            #             "model": "runware:105@1"
            #         }
            #         ]
            #     }
            #     ]
            openposeTaskUUID = str(uuid.uuid4())
            depthTaskUUID = str(uuid.uuid4())
            softedgeTaskUUID = str(uuid.uuid4())
            controlnetPayload = [
                {
                "taskType": "imageControlNetPreProcess",
                "taskUUID": openposeTaskUUID,
                "inputImage": imageUUID,
                "preProcessorType": "openpose",
                "height": 512,
                "width": 768
                },
                {
                "taskType": "imageControlNetPreProcess",
                "taskUUID": depthTaskUUID,
                "inputImage": imageUUID,
                "preProcessorType": "depth",
                "height": 512,
                "width": 768
                },
                {
                "taskType": "imageControlNetPreProcess",
                "taskUUID": softedgeTaskUUID,
                "inputImage": imageUUID,
                "preProcessorType": "softedge",
                "height": 512,
                "width": 768
                }
            ]

            response = session.post(url=url, json=controlnetPayload, headers=headers)
            if response.ok :
                r = json.loads(response.text)
            else:
                logger.debug( "Controlnet request to runware.ai failed")
                raise RuntimeError("Controlnet request to runware.ai failed")
            guideImages = {
                "depth": "", "openpose": "", "softedge": ""
            }
            data = r["data"];

            for controlnetResponse in data:
                if( controlnetResponse["taskUUID"] == openposeTaskUUID ):
                    guideImages["openpose"] = controlnetResponse["guideImageUUID"]
                if( controlnetResponse["taskUUID"] == depthTaskUUID ):
                    guideImages["depth"] = controlnetResponse["guideImageUUID"]
                if( controlnetResponse["taskUUID"] == softedgeTaskUUID ):
                    guideImages["softedge"] = controlnetResponse["guideImageUUID"]

            # Dreamshaper
            model = "civitai:4384@128713"
            
            imageInferencePayload = [{
                "taskType": "imageInference",
                "taskUUID": str(uuid.uuid4()),
                "positivePrompt": params["prompt"],
                "negativePrompt": "disfigured, blurry, nude",
                #"seedImage": imageUUID,
                "scheduler": params["sampler_name"] + " " + params["scheduler"],
                "model": model,
                "height": int(params["height"]),
                "width": int(params["width"]),
                "strength": 0.25,
                "outputType": "base64Data",
                "controlNets": [{
                    "model": "civitai:38784@44811", #openpose
                    "startStepPercentage": 0,
                    "endStepPercentage": 100,
                    "guideImage": guideImages["openpose"],
                    "weight": params["openpose"]["weight"],
                    "controlMode": "balanced"
                },{
                    "model": "civitai:38784@44736", #depth
                    "startStepPercentage": 0,
                    "endStepPercentage": 100,
                    "guideImage": guideImages["depth"],
                    "weight": params["depth"]["weight"],
                    "controlMode": "balanced"
                },
                {
                    "model": "civitai:38784@44756", #softedge
                    "startStepPercentage": 0,
                    "endStepPercentage": 100,
                    "guideImage": guideImages["softedge"],
                    "weight": params["softedge"]["weight"],
                    "controlMode": "balanced"
                }
                ]
            }
            ]
            response = session.post(url=url, json=imageInferencePayload, headers=headers)
            # response = session.post(url=url, json=fluxPayload, headers=headers) 
            if response.ok :
                r = json.loads(response.text)
            else:
                logger.debug( "imageReference request to runware.ai failed: " + repr( response ))
            
            data = r["data"]
            #logger.debug( "ImageInference response from runware.ai: " + repr ( r ))
            resImage = data[0]["imageBase64Data"]
            #fluxPayload[0]["seedImage"]= ""
            
            

            image = Image.open(io.BytesIO(base64.b64decode( resImage )))

            return image

            # optionally set username, password when --api-auth=username:password is set on webui.
            # username, password are not protected and can be derived easily if the communication channel is not encrypted.
            # you can also pass username, password to the WebUIApi constructor.
            # api.set_auth('username', 'password')

        except Exception as exc:
            raise RuntimeError(f"error processing the filter {self.filter}") from exc

    def __repr__(self) -> str:
        return self.__class__.__name__


def to_camelcase(s):
    s = sub(r"(_|-)+", " ", s).title().replace(" ", "").replace("*", "")
    return "".join([s[0].upper(), s[1:]])


def merge_nested_dicts(dict1, dict2):
    res = {}
    for key, value in dict1.items():
        if key in dict2:
            res[key] = merge_nested_dicts(dict1[key], dict2[key])
            del dict2[key]
        else:
            res[key] = value
    res.update(dict2)
    return res

# Stunning Image Styles using Stable Diffusion from within the Photobooth-App

There are dozens of online services with allow to modify or enhance your images using "AI", but this approach uses local-only services with <https://github.com/lllyasviel/stable-diffusion-webui-forge> running in the background either on the machine running photobooth-app or a separate computer.
Stable Diffusion WebUI Forge runs on both Windows and Linux - but it requires a dedicated graphics adapter with 8GB or more VRAM.
WebUI Forge can be used via API, so we can use it from the Photobooth-App.

## Installation of Stable-Diffusion-WebUI Forge and Setup

For the general installation, just follow the setup instructions in [their Github Page](https://github.com/lllyasviel/stable-diffusion-webui-forge).
You **must** enable the API with `--api` in the `COMMANDLINE_ARGS` variable. If you don't run the photobooth-app on the same computer, you also need to listen on a reachable IP with `--listen`. So on a Windows system, open up the file (/webui/webui-user.bat) and change
set COMMANDLINE_ARGS=
to
set COMMANDLINE_ARGS=--api --listen

## Stable-Diffusion-WebUI Models

The models are most important, but the additional control nets are an essential part of getting pictures with some resemblance at all.

### StableDiffusion

These are the models/LoRa/ControlNets that need to be present in your stable-diffusion-webui-forge instance.
The base models are found across [huggingface.co](https://huggingface.co/) and [civtai.com](https://civitai.com/). Put these files into the folder "/webui/models/Stable-Diffusion":

* [DreamShaper 8 pruned by Lykon](https://civitai.com/models/4384/dreamshaper), direct link: [dreamshaper8Pruned.hz5Q.safetensors](https://civitai.com/api/download/models/128713?type=Model&format=SafeTensor&size=pruned&fp=fp16)<br>`879db523c30d3b9017143d56705015e15a2cb5628762c11d086fed9538abd7fd`

* [AbsoluteReality v1.8.1 by Lykon](https://civitai.com/models/81458/absolutereality), direct link: [absolutereality181.n8IR.safetensors](https://civitai.com/api/download/models/132760?type=Model&format=SafeTensor&size=pruned&fp=fp16)<br>`463d6a9fe8a4b56a4d69ef3692074c0617428dfd8e8f12f9efe3b1e9a71717ce`

* [Anime Pastel Dream by Lykon](https://civitai.com/models/23521/anime-pastel-dream), direct link: [animepasteldreamSoft.lTTK.safetensors](https://civitai.com/api/download/models/28100?type=Model&format=SafeTensor&size=full&fp=fp16)<br>`4be38c1a1782d428772b78c0e2a773b08324069fc3cf2c040bc492c4e1a18976`

* [Western Animation Diffusion v1 by Lykon](https://civitai.com/models/86546?modelVersionId=92044), direct link: [westernanidiffusion.EpVW.safetensors](https://civitai.com/api/download/models/92044?type=Model&format=SafeTensor&size=pruned&fp=fp16)<br>`d20bc9d543b7d7d46a3ed7d91edc1880d8423f1a8a77dcf378801b5dbe211c3b`

* [Caricaturizer v1 by Clumsy_Trainer](https://civitai.com/models/1096/caricaturizer), direct link: [caricaturizer_pcrc_style.uwgn1lmj.q5b.ckpt](https://civitai.com/api/download/models/1097?type=Model&format=PickleTensor&size=full&fp=fp16)<br>`0a7a6a397b12a5a0528f927e4607ab31b641fb5ea9b532967b4770485d76fb67`

* [Clazy clazy2600 by Clumsy_trainer](https://civitai.com/models/82/clazy), direct link: [clazy2600.xYzn.ckpt](https://civitai.com/api/download/models/92?type=Model&format=PickleTensor&size=full&fp=fp16)<br>`ed2cf308d1f8a6e3373e121d755d4e191c3d3a0dad0220e82bff95c51eb84458`

### LoRa

Additionally, these LoRAs are needed for some presets:

* [KIDS Illustration CoolKids v2 by Clumsy_Trainer](https://civitai.com/models/60724/kids-illustration), direct link: [coolkidsMERGEV25.Qqci.safetensors](https://civitai.com/api/download/models/67980?type=Model&format=SafeTensor)<br>`461a1dc302a1bd5e25fce75644e50ec589ac4f65573238709fb415b7aaf1eb36`

* [ClayAnimationRedmond v1.0 by artificialguybr](https://civitai.com/models/205830/clayanimationredmond-15-version-clay-animation-lora-for-liberte-redmond-sd-15?modelVersionId=231740), direct link: [ClayAnimationRedmond15-ClayAnimation-Clay.safetensors](https://civitai.com/api/download/models/231740?type=Model&format=SafeTensor)<br>`bdd7d38cf00fa7e800422372dee5ef93e09de627e712f0902efc32dcd20cfffe`

* [GOTCHA! v1.0 by Clumsy_Trainer](https://civitai.com/models/76408/gotcha), direct link: [gotchaV001.Yu4Z.safetensors](https://civitai.com/api/download/models/81183?type=Model&format=SafeTensor)<br>`512e935475fb1e469495cf311eee606bf39e9f5fd0239d8aebc7e01fb3f2e7e2`

* [Modill Pastell v1.0 by Clumsy_Trainer](https://civitai.com/models/103158/modill-pastell-modern-style-illustration-lora), direct link: [modillPASTELRCV001.xsmb.safetensors](https://civitai.com/api/download/models/110428?type=Model&format=SafeTensor)<br>`34fc8a925ffa408fc3c2354b7b37df2212a59fb6fd14e3903c8de3214ba5c3fd`

* [NEOTOKIO v1.0 by Clumsy_Trainer](https://civitai.com/models/78374/neotokio), direct link: [neotokioV001.yBGi.safetensors](https://civitai.com/api/download/models/83179?type=Model&format=SafeTensor)<br>`bd23a2107c72df13748d1e92a72fefd71cd56fd96eb2eb4abe2287c0d9b9b73c`

* [Watercolor v1.0 by Clumsy_Trainer](https://civitai.com/models/64560/watercolor), direct link: [watercolorv1.7lox.safetensors](https://civitai.com/api/download/models/69190?type=Model&format=SafeTensor)<br>`6c94b5fe6ef44e67c42f7912dc5e639468e3e53cd24c304ba3b49df96e23164c`

Put these files into the folder "/webui/models/Lora".

### ControlNets

For ControlNets, use the [ControlNet v1.1 models by lllyasviel](https://huggingface.co/lllyasviel/ControlNet-v1-1/tree/main):

* Depth: [control_v11f1p_sd15_depth.pth](https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11f1p_sd15_depth.pth?download=true)<br>`761077ffe369fe8cf16ae353f8226bd4ca29805b161052f82c0170c7b50f1d99`
* OpenPose: [control_v11p_sd15_openpose.pth](https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_openpose.pth?download=true)<br>`db97becd92cd19aff71352a60e93c2508decba3dee64f01f686727b9b406a9dd`
* SoftEdge: [control_v11p_sd15_softedge.pth](https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_softedge.pth?download=true)<br>`20759ef71a109c4796e637d86eea8db492ec9772b6d5cb7a9afd077847b403f3`
* Canny: [control_v11p_sd15_canny.pth](https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_canny.pth?download=true)<br>`f99cfe4c70910e38e3fece9918a4979ed7d3dcf9b81cee293e1755363af5406a`

The Controlnets need to be placed in the folder "/webui/models/ControlNet".

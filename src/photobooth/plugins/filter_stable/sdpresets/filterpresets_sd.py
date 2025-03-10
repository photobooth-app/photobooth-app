from .basefiltersd import BaseFilterSD

clay = BaseFilterSD()

clay.prompt = (
    "Clay Animation, Clay, clazy style, claymation, stopmotion, small clay figure, vibrant colors, fantastic plastic <lora:ClayAnimationRedmond15-ClayAnimation-Clay:0.7>"
    + clay.prompt
)
# ClayFilterSD.depth.weight = 0.7
# ClayFilterSD.openpose.weight = 0.8
# ClayFilterSD.softedge.weight = 0.4

gotcha = BaseFilterSD()

gotcha.prompt = (
    "stylized cartoon, illustration, portrait of persons and an animal, looking sideways, forest in the background <lora:gotchaV001.Yu4Z:0.4>"
    + gotcha.prompt
)
# GotchaFilterSD.depth.weight = 0.7
# GotchaFilterSD.openpose.weight = 0.8
# GotchaFilterSD.softedge.weight = 0.4

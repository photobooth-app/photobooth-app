# Notes

## Video source

The video licensed from

- <https://www.pond5.com/de/stock-footage/item/59529661-two-boy-and-pretty-girl-are-making-photos-photo-accessories>

## Convert command

```sh
ffmpeg -hide_banner -loglevel info -y -i .\input.avi -filter:v crop=1080:720:200:0,scale=-2:720,setsar=1:1,fps=15 -vcodec mjpeg -q:v 3 -an demovideo.mjpg
```

- `-q`: switch valid range is 1-31 (lower being better quality)
- `-vcodec mjpeg`: output raw jpeg images concatenated in a mjpg file
- `-filter:v scale=-2:960,setsar=1:1,fps=15`: resize to 960 pixel height, keep aspect ratio, target framerate 15
- `crop=1080:720:200:0,`: width,height,x,y

Since the video is packaged in the pypi package, the size needs to be kept to a reasonable amount and tends to be on the lower side.

# Notes

## Video source

The videos were downloaded from

- <https://www.vecteezy.com/video/34488133-smiling-man-and-woman-in-love-look-into-boxes>

## Convert command

```bash
ffmpeg -y -i .\input.avi -filter:v scale=-2:960,setsar=1:1,fps=15 -vcodec mjpeg -q:v 3 -an demovideo.mjpg
```

- `-q`: switch valid range is 1-31 (lower being better quality)
- `-vcodec mjpeg`: output raw jpeg images concatenated in a mjpg file
- `-filter:v scale=-2:960,setsar=1:1,fps=15`: resize to 960 pixel height, keep aspect ratio, target framerate 15

Since the video is packaged in the pypi package, the size needs to be kept to a reasonable amount and tends to be on the lower side.

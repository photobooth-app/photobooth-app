# AI Restyler

The AI Restyler is a built-in image filter plugin that transforms photos into
different visual styles while aiming to preserve the people, pose, and
composition in the original image. It can be used in the image processing
pipeline or offered as a filter users can choose in the gallery.

## Providers

Choose a provider in the plugin configuration. The provider settings are
selected with a discriminator, so only the settings for the active provider
are shown:

- **Replicate** — cloud inference using a Replicate model and API token.
- **fal.ai** — cloud inference using a fal.ai model and API key.
- **ComfyUI** — local inference using a ComfyUI API server and an API-format
  workflow.

Cloud providers send the input image to that service and may charge for each
request. Make sure guests are informed when using a cloud provider. ComfyUI
can keep processing local, depending on how its server and models are hosted.

## Styles and previews

The plugin includes presets such as cartoon, anime, 3D animation, medieval,
renaissance, comic book, superhero, pop art, watercolor, pencil sketch, cyberpunk,
1920s, and brick figures. Administrators can add, edit, or remove styles in
the plugin configuration. Each style has a name and a prompt description;
styles may also define a negative prompt for compatible ComfyUI workflows.
Restart the app after changing the style list.
Updated defaults do not replace saved prompt templates or style lists; update
them in the plugin configuration if you want to use the new prompts.

The plugin includes bundled preview images for all built-in styles. These
previews do not make provider requests. An administrator can set a custom
preview image for a style. A style with no preview image and no matching
bundled image displays the original photo.
Preview images are center-cropped to the photo's aspect ratio and converted to
RGB without resizing. Supply custom previews at the desired resolution.

## Common settings

The `common` configuration group contains:

- **Enabled** — turns on AI processing.
- **Prompt template** — the shared prompt sent to the model. `{style}` is
  replaced by the selected style's prompt.
- **Max input size** — maximum width or height sent to the provider; the
  result is resized to the original image dimensions.
- **Max concurrent requests** — limits simultaneous provider requests.
- **Cache max entries** — maximum number of cached results. Set to `0` to
  disable caching.
- **Add userselectable filter** — makes styles marked user-selectable
  available in the gallery.

Processed results are cached locally to avoid repeat requests for the same
image, prompt, and model.

## Replicate test result

Replicate was tested with this plugin. In that test, an image took about
**4 seconds** to render and cost approximately **$0.04**. This is an observed
result, not a performance or price guarantee; render time and cost vary with
the selected model, image, provider load, and current provider pricing.

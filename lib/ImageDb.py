
class ImageDb():
    """Handle all image related stuff"""

    def __init__(self):
        self.image_cache = None

        self._update_cache()

    def _update_cache(self):
        pass

    def getImages(self):
        pass

    def getImage(self, filename):
        pass

    def addNewImage(self, frame):
        """
        A newly captured frame was taken by camera, now its up to this class to create the thumbnail, preview
        finally event is sent when processing is finished
        """
        pass

    def deleteImage(self, filename):
        """ delete single file and it's related thumbnails """
        pass

    def deleteImages(self):
        """ delete all images, inclusive thumbnails, ..."""
        pass

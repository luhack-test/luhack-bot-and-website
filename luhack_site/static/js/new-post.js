Dropzone.options.imageUploadDropzone = {
  acceptedFiles: "image/png,image/jpeg,image/jpg,image/gif,image/webp",
  init: function() {
    var existing_images = JSON.parse(
      document.getElementById("image-upload-dropzone").dataset.existingImages
    );

    var _this = this;

    existing_images.forEach(image => {
      var mockFile = { name: image.filename, size: 1234, dataURL: image.path };

      this.emit("addedfile", mockFile);
      this.createThumbnailFromUrl(
        mockFile,
        this.options.thumbnailWidth,
        this.options.thumbnailHeight,
        this.options.thumbnailMethod,
        true,
        function(dataUrl) {
          _this.emit("thumbnail", mockFile, dataUrl);
          _this.emit("success", mockFile, image);
          _this.emit("complete", mockFile);
        }
      );
    });

    this.on("success", function(file, resp) {
      var remove_button = Dropzone.createElement("<button>Delete</button>");

      var _this = this;

      remove_button.addEventListener("click", function(e) {
        e.preventDefault();
        e.stopPropagation();

        fetch(resp.path, {
          method: "delete"
        }).then(function(_) {
          _this.removeFile(file);
        });
      });

      file.previewElement.appendChild(remove_button);

      var filename_node = file.previewTemplate.getElementsByClassName(
        "dz-filename"
      )[0].childNodes[0];

      filename_node.textContent = `![](/images/${resp.filename})`;
    });
  }
};

const tags_input = document.getElementById("tags");
const existing_tags = JSON.parse(tags_input.dataset.tagsWhitelist);
const tags_tagify = new Tagify(tags_input, {
  whitelist: existing_tags,
  delimiters: ", ",
  maxTags: 8,
});

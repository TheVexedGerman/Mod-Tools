A collection of tools for moderating.

---

# Building dockers

The images try to source a prebuild image with opencv already installed. That one is based on the python3.9-bullseye docker.

The `build_dockers.sh` script will try to build and push all images. It has a couple of options which should be customized, such as the repository url to which the images should be pushed.
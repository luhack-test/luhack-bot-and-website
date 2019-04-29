import imghdr
from typing import List, Tuple

import ujson
import sqlalchemy as sa
from starlette.endpoints import HTTPEndpoint
from starlette.requests import HTTPConnection
from starlette.responses import Response, UJSONResponse
from starlette.authentication import requires
from starlette.routing import Router

from luhack_bot.db.models import Image

from luhack_site.authorization import can_edit
from luhack_site import converters

# magick happens here
converters.inject()

router = Router()


@router.route("/{file_name:file}", name="images")
class Images(HTTPEndpoint):
    async def get(self, request: HTTPConnection):
        uuid, ext = request.path_params["file_name"]

        image = await Image.get(uuid)

        if image.filetype != ext:
            return abort(404)

        return Response(image.image, media_type=f"image/{image.filetype}")

    @requires("authenticated")
    async def delete(self, request: HTTPConnection):
        uuid, ext = request.path_params["file_name"]

        image = await Image.get(uuid)

        if image.filetype != ext:
            return abort(404)

        if not can_edit(request, image.author_id):
            return abort(400)

        await image.delete()

        return Response()


@router.route("/upload", methods=["POST"])
@requires("authenticated", redirect="need_auth")
async def image_upload(request: HTTPConnection):
    form = await request.form()

    file_contents = await form["file"].read()

    filetype = imghdr.what("dynamic", file_contents)
    if filetype not in {"png", "jpeg", "gif", "webp"}:
        return abort(400, "Bad image type")

    file = await Image.create(
        author_id=request.user.discord_id, filetype=filetype, image=file_contents
    )

    return UJSONResponse({"filename": f"{file.id}.{filetype}"})


async def get_existing_images(author_id: int) -> List[Tuple[str, str]]:
    return (
        await sa.select([Image.id, Image.filetype])
        .where(Image.author_id == author_id)
        .gino.all()
    )


async def encoded_existing_images(request: HTTPConnection) -> str:
    images = await get_existing_images(request.user.discord_id)
    images = [
        {
            "filename": f"{id}.{ext}",
            "path": request.url_for("images", file_name=(id, ext)),
        }
        for (id, ext) in images
    ]
    return ujson.dumps(images)

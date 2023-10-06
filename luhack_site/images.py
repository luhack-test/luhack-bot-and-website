import imghdr
from typing import List, Tuple

import orjson
import sqlalchemy as sa
from starlette.endpoints import HTTPEndpoint
from starlette.requests import HTTPConnection
from starlette.responses import Response, JSONResponse
from starlette.authentication import requires
from starlette.routing import Router

from luhack_bot.db.models import Image

from luhack_site.utils import abort
from luhack_site.authorization import can_edit
from luhack_site import converters

# magick happens here
converters.inject()

router = Router()


class ORJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return orjson.dumps(content)


@router.route("/{file_name:file}", name="images")
class Images(HTTPEndpoint):
    async def get(self, request: HTTPConnection):
        uuid, ext = request.path_params["file_name"]

        image = await Image.get(uuid)

        if image is None or image.filetype != ext:
            return abort(404)

        headers = {
            "Cache-Control": "public, max-age=604800, immutable",
        }

        return Response(image.image, media_type=f"image/{image.filetype}", headers=headers)

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

    return ORJSONResponse({"filename": f"{file.id}.{filetype}"})


async def get_existing_images(author_id: int) -> List[Tuple[str, str]]:
    return (
        await sa.select([Image.id, Image.filetype])
        .where(Image.author_id == author_id)
        .gino.all()
    )


async def encoded_existing_images(request: HTTPConnection) -> bytes:
    images = await get_existing_images(request.user.discord_id)
    images = [
        {
            "filename": f"{id}.{ext}",
            "path": str(request.url_for("images", file_name=(id, ext))),
        }
        for (id, ext) in images
    ]
    return orjson.dumps(images)

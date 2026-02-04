import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

static_router = APIRouter(prefix="/static", tags=["static"])

UPLOAD_DIR = "static/cars"


@static_router.get("/cars/{filename}")
async def get_car_image(filename: str):
    """
    Serves car images.
    Publicly accessible via UUID-based filenames.
    """
    file_path = os.path.join(UPLOAD_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")

    # FileResponse is efficient; it handles chunking and headers for you
    return FileResponse(file_path)


# @static_router.delete("/{filename}")
# async def delete_car_image(filename: str, user=Depends(FastJWT().login_required)):
#     owner_id = filename.split("-")[0]
#     if str(user.id) != owner_id:
#         raise HTTPException(
#             status_code=403, detail="Not authorized to delete this photo"
#         )

#     file_path = os.path.join(UPLOAD_DIR, filename)
#     if os.path.exists(file_path):
#         os.remove(file_path)
#     return {"detail": "File deleted"}

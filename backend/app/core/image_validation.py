"""
Validation partagée pour les champs image encodés en base64 (logo
d'établissement, signature et tampon personnels). Aucun service de stockage
de fichiers externe n'est intégré : les images sont stockées directement en
base sous forme de data URI, avec une limite de taille pour éviter qu'un envoi
abusif ne gonfle démesurément la base de données.

Ces images sont IMPRIMÉES sur les documents officiels (bulletins). Elles sont
donc validées à l'envoi — et pas seulement à l'impression — sur trois points :
  * format : PNG, JPEG, WebP ou GIF uniquement. Le SVG est refusé : il ne peut
    pas être rendu dans un PDF, et acceptait auparavant un fichier qui
    disparaissait ensuite en silence du bulletin ;
  * intégrité : le fichier est réellement décodé (un base64 corrompu, ou un
    autre type de fichier renommé en image, est rejeté) ;
  * dimensions : plafonnées, pour écarter les « bombes de décompression »
    (petit fichier compressé qui s'ouvre en image gigantesque).
"""
import base64
import binascii
import io
import re

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BASE64_LENGTH = 1_500_000  # ~1.1 Mo binaire une fois décodé, large pour un logo/signature/tampon
MAX_IMAGE_PIXELS = 16_000_000        # ex. 4000 × 4000
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}

_DATA_URI = re.compile(r"data:image/(?:png|jpeg|jpg|webp|gif);base64,(?P<payload>[A-Za-z0-9+/=]+)")
_UNSUPPORTED = "Format d'image non pris en charge : utilisez une image PNG, JPEG, WebP ou GIF (le SVG ne peut pas être imprimé sur les documents)."


def validate_image_data_uri(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.startswith("data:image/"):
        raise ValueError("L'image doit être fournie au format data URI (data:image/...;base64,...).")
    if len(value) > MAX_IMAGE_BASE64_LENGTH:
        raise ValueError("Image trop volumineuse (1 Mo maximum environ).")
    match = _DATA_URI.fullmatch(value)
    if match is None:
        raise ValueError(_UNSUPPORTED)
    try:
        raw = base64.b64decode(match.group("payload"), validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            image_format = image.format
            width, height = image.size
            image.verify()  # contrôle l'intégrité du fichier sans le décoder entièrement
    except (binascii.Error, UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise ValueError("Image illisible ou corrompue : envoyez un fichier PNG, JPEG, WebP ou GIF valide.")
    if image_format not in ALLOWED_FORMATS:
        raise ValueError(_UNSUPPORTED)
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError("Image trop grande en dimensions (16 millions de pixels maximum, par exemple 4000 × 4000).")
    return value

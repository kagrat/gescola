"""
Validation partagée pour les champs image encodés en base64 (logo
d'établissement, signature et tampon personnels). Aucun service de stockage
de fichiers externe n'est intégré dans ce livrable — les images sont stockées
directement en base sous forme de data URI, avec une limite de taille pour
éviter qu'un envoi abusif ne gonfle démesurément la base de données.
"""
MAX_IMAGE_BASE64_LENGTH = 1_500_000  # ~1.1 Mo binaire une fois décodé, large pour un logo/signature/tampon


def validate_image_data_uri(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.startswith("data:image/"):
        raise ValueError("L'image doit être fournie au format data URI (data:image/...;base64,...).")
    if len(value) > MAX_IMAGE_BASE64_LENGTH:
        raise ValueError("Image trop volumineuse (1 Mo maximum environ).")
    return value

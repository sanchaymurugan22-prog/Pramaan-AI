"""Stage 8: the languages, and what this computer can do in each.

GET /api/languages   the 23 languages (English + the 22 of the Eighth Schedule) with their names, script and
                     writing direction, SMS limit, and whether translation, a voice (narration) and
                     speech-to-text are available here. Used by every language picker in the app.
"""

from fastapi import APIRouter, Depends

from app.auth.deps import signed_in
from app.db import User
from app.lang import languages, stt, translate, tts

router = APIRouter(prefix="/api", tags=["languages"])


@router.get("/languages")
def list_languages(user: User = Depends(signed_in)):
    t, voices = translate.status(), tts.status()["voices"]
    return {
        "translation": t,
        "languages": [
            {"code": lang.code, "name": lang.name, "native": lang.native, "script": lang.script, "rtl": lang.rtl,
             "sms_limit": lang.sms_limit,
             "translate": lang.code == "en" or t["ready"],
             "voice": voices[lang.code]["name"] if lang.code in voices else None,
             "speech_to_text": stt.ready(lang.code)}
            for lang in languages.LANGUAGES.values()
        ],
    }

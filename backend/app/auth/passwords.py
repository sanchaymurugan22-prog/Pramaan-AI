"""Passwords: hashing (argon2id), the password rules, and temporary passwords.

Passwords are never stored, logged or sent back. Only the argon2id hash is saved: a slow, salted,
one-way fingerprint, so even someone with a copy of the database cannot read the passwords.
"""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# argon2-cffi's defaults are argon2id with 64 MB memory and 3 passes (RFC 9106 "low memory" profile):
# about 50-100 ms per check on the dev laptop, which makes guessing very slow.
_hasher = PasswordHasher()

MIN_LENGTH = 12
MAX_LENGTH = 128  # a very long "password" would make hashing slow on purpose

# Passwords people pick when told "at least 12 characters". Checked in lower case.
_TOO_COMMON = {
    "password1234", "password12345", "password123456", "123456789012", "1234567890123", "qwertyuiopas",
    "qwerty123456", "abcdefghijkl", "abc123456789", "passwordpassword", "welcome12345", "admin1234567",
    "iloveyou1234", "letmein12345", "pramaanai123", "pramaan12345", "india1234567",
}


class PasswordRuleError(ValueError):
    """The new password does not follow the rules. The message says why, in plain words."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """True if the password matches the hash. Never raises for a wrong password."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True if the hash was made with older (weaker) settings; it is replaced at the next sign-in."""
    return _hasher.check_needs_rehash(password_hash)


# Checked against when the username does not exist, so a wrong username takes as long as a wrong
# password (otherwise the time taken would tell an attacker which usernames exist).
_DUMMY_HASH = _hasher.hash(secrets.token_hex(16))


def waste_time_like_a_check(password: str) -> None:
    verify_password(_DUMMY_HASH, password)


def check_rules(password: str, username: str = "", full_name: str = "") -> None:
    """Raise PasswordRuleError if the password is not allowed."""
    if len(password) < MIN_LENGTH:
        raise PasswordRuleError(f"The password must be at least {MIN_LENGTH} characters long.")
    if len(password) > MAX_LENGTH:
        raise PasswordRuleError(f"The password must be at most {MAX_LENGTH} characters long.")
    lowered = password.lower()
    if len(set(password)) < 4:
        raise PasswordRuleError("The password repeats the same few characters. Use a longer mix, "
                                "for example three random words and a number.")
    if lowered in _TOO_COMMON:
        raise PasswordRuleError("This password is too common. Try three random words and a number.")
    if username and len(username) >= 3 and username.lower() in lowered:
        raise PasswordRuleError("The password must not contain your username.")
    for part in full_name.lower().split():
        if len(part) >= 4 and part in lowered:
            raise PasswordRuleError("The password must not contain your name.")


# Short, easy-to-read words for temporary passwords (read out or written down by the Admin).
_WORDS = (
    "tulsi river kamal neem peepal mango lotus tiger peacock ganga yamuna kaveri godavari narmada monsoon "
    "chai masala sitar tabla veena diya rangoli kolam banyan cobra falcon koel myna parrot sparrow "
    "elephant camel desert himalaya ghats delta island harbour lantern kite pebble meadow orchard saffron "
    "indigo emerald amber silver copper marble granite coral pearl jasmine marigold hibiscus cedar teak "
    "sandal bamboo spice pepper ginger cardamom clove cumin mustard wheat millet barley paddy harvest "
    "comet planet orbit rocket signal beacon compass anchor bridge tunnel canal market bazaar"
).split()


def temporary_password() -> str:
    """e.g. "tulsi-river-7429-kamal": 3 random words and a 4-digit number (about 32 bits of chance;
    fine for a one-time password, because 5 wrong tries lock the account).
    Used once: the person must choose their own password at the next sign-in."""
    words = [secrets.choice(_WORDS) for _ in range(3)]
    number = f"{secrets.randbelow(10000):04d}"
    return "-".join(words[:2] + [number] + words[2:])

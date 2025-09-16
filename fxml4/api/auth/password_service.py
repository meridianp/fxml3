"""
Password Hashing and Validation Service for FXML4
=================================================

Enterprise-grade password management service with:
- Secure bcrypt hashing with configurable rounds
- Comprehensive password complexity validation
- Password history tracking and reuse prevention
- Password expiry and rotation support
- Password strength scoring and breach checking
- Cryptographically secure password generation
"""

import hashlib
import re
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import bcrypt
import requests

from .models import PasswordValidationResult


class PasswordService:
    """Password hashing and validation service with enterprise security features."""

    # Default security configuration
    DEFAULT_MIN_LENGTH = 8
    DEFAULT_MAX_PASSWORD_AGE_DAYS = 90
    DEFAULT_PASSWORD_HISTORY_COUNT = 5
    DEFAULT_BCRYPT_ROUNDS = 12

    # Character sets for validation and generation
    UPPERCASE_CHARS = string.ascii_uppercase
    LOWERCASE_CHARS = string.ascii_lowercase
    DIGIT_CHARS = string.digits
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    # Common weak passwords (subset - in production, use comprehensive list)
    COMMON_PASSWORDS = {
        "password",
        "123456",
        "123456789",
        "qwerty",
        "abc123",
        "password123",
        "admin",
        "letmein",
        "welcome",
        "monkey",
        "dragon",
        "pass",
        "master",
        "hello",
        "freedom",
    }

    def __init__(
        self,
        min_length: int = DEFAULT_MIN_LENGTH,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digits: bool = True,
        require_special_chars: bool = True,
        max_password_age_days: int = DEFAULT_MAX_PASSWORD_AGE_DAYS,
        password_history_count: int = DEFAULT_PASSWORD_HISTORY_COUNT,
        bcrypt_rounds: int = DEFAULT_BCRYPT_ROUNDS,
        enable_breach_checking: bool = True,
    ):
        """
        Initialize password service.

        Args:
            min_length: Minimum password length
            require_uppercase: Require uppercase letters
            require_lowercase: Require lowercase letters
            require_digits: Require numeric digits
            require_special_chars: Require special characters
            max_password_age_days: Maximum password age before expiry
            password_history_count: Number of old passwords to remember
            bcrypt_rounds: bcrypt work factor (4-15, default 12)
            enable_breach_checking: Enable breach checking via HaveIBeenPwned
        """
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digits = require_digits
        self.require_special_chars = require_special_chars
        self.max_password_age_days = max_password_age_days
        self.password_history_count = password_history_count
        self.bcrypt_rounds = bcrypt_rounds
        self.enable_breach_checking = enable_breach_checking

        # In-memory storage for password history (use database in production)
        self._password_histories: Dict[str, List[Tuple[str, datetime]]] = {}

        # Validate bcrypt rounds
        if not (4 <= bcrypt_rounds <= 15):
            raise ValueError("bcrypt rounds must be between 4 and 15")

    def hash_password(self, password: str, rounds: Optional[int] = None) -> str:
        """
        Hash password using bcrypt.

        Args:
            password: Plain text password to hash
            rounds: bcrypt work factor (overrides default)

        Returns:
            Bcrypt hash string

        Raises:
            ValueError: If password is empty
        """
        if not password:
            raise ValueError("Password cannot be empty")

        if rounds is None:
            rounds = self.bcrypt_rounds

        # Generate salt and hash
        salt = bcrypt.gensalt(rounds=rounds)
        password_bytes = password.encode("utf-8")
        hashed = bcrypt.hashpw(password_bytes, salt)

        return hashed.decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify password against hash (timing-safe).

        Args:
            password: Plain text password to verify
            password_hash: Stored bcrypt hash

        Returns:
            True if password matches, False otherwise

        Raises:
            ValueError: If hash format is invalid
        """
        if not password_hash.startswith("$2b$"):
            raise ValueError("Invalid hash format")

        try:
            password_bytes = password.encode("utf-8")
            hash_bytes = password_hash.encode("utf-8")

            # bcrypt.checkpw is timing-safe
            return bcrypt.checkpw(password_bytes, hash_bytes)
        except Exception as e:
            raise ValueError(f"Hash verification failed: {e}")

    def validate_password(
        self, password: str, user_id: Optional[str] = None
    ) -> PasswordValidationResult:
        """
        Validate password complexity and security requirements.

        Args:
            password: Password to validate
            user_id: User ID for history checking (optional)

        Returns:
            PasswordValidationResult with validation details
        """
        errors = []

        # Length check
        if len(password) < self.min_length:
            errors.append(
                f"Password must be at least {self.min_length} characters long"
            )

        # Character requirements
        if self.require_uppercase and not re.search(r"[A-Z]", password):
            errors.append("Password must contain uppercase letters")

        if self.require_lowercase and not re.search(r"[a-z]", password):
            errors.append("Password must contain lowercase letters")

        if self.require_digits and not re.search(r"[0-9]", password):
            errors.append("Password must contain digits")

        if self.require_special_chars and not re.search(
            f"[{re.escape(self.SPECIAL_CHARS)}]", password
        ):
            errors.append("Password must contain special characters")

        # Common password check
        if password.lower() in self.COMMON_PASSWORDS:
            errors.append("Password is too common and easily guessable")

        # Sequential characters check (only for obvious patterns)
        if self._has_obvious_sequential_chars(password):
            errors.append("Password contains obvious sequential patterns")

        # Repeated characters check
        if self._has_repeated_chars(password):
            errors.append("Password contains too many repeated characters")

        # Password reuse check
        if user_id and self.is_password_reused(user_id, password):
            errors.append("Password was used recently and cannot be reused")

        # Breach checking (optional, requires network) - only if no other errors
        if self.enable_breach_checking and len(errors) == 0:
            try:
                if self.check_password_breach(password):
                    errors.append("Password found in known data breaches")
            except Exception:
                # Don't fail validation due to network issues
                pass

        return PasswordValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            strength_score=(
                self.calculate_password_strength(password) if len(errors) == 0 else 0
            ),
        )

    def _has_obvious_sequential_chars(self, password: str) -> bool:
        """Check for obvious sequential patterns (123, abc, qwerty)."""
        password_lower = password.lower()

        # Check for 4+ sequential digits (e.g., 1234, 9876)
        for i in range(len(password) - 3):
            if password[i : i + 4].isdigit():
                digits = [int(d) for d in password[i : i + 4]]
                # Check for strictly increasing or decreasing sequence of 4+
                if all(digits[j + 1] - digits[j] == 1 for j in range(3)) or all(
                    digits[j] - digits[j + 1] == 1 for j in range(3)
                ):
                    return True

        # Check for obvious keyboard patterns
        obvious_patterns = ["qwer", "asdf", "zxcv", "1234", "4321", "abcd", "dcba"]

        for pattern in obvious_patterns:
            if pattern in password_lower or pattern[::-1] in password_lower:
                return True

        return False

    def _has_repeated_chars(self, password: str) -> bool:
        """Check for excessive repeated characters."""
        # More than 3 consecutive identical characters
        for i in range(len(password) - 3):
            if len(set(password[i : i + 4])) == 1:
                return True

        # More than 50% repeated characters
        char_counts = {}
        for char in password:
            char_counts[char] = char_counts.get(char, 0) + 1

        max_count = max(char_counts.values()) if char_counts else 0
        if max_count > len(password) * 0.5:
            return True

        return False

    def calculate_password_strength(self, password: str) -> int:
        """
        Calculate password strength score (0-4).

        Args:
            password: Password to score

        Returns:
            Strength score: 0=Very Weak, 1=Weak, 2=Fair, 3=Strong, 4=Very Strong
        """
        score = 0

        # Length scoring
        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1

        # Character diversity
        has_lower = bool(re.search(r"[a-z]", password))
        has_upper = bool(re.search(r"[A-Z]", password))
        has_digit = bool(re.search(r"[0-9]", password))
        has_special = bool(re.search(f"[{re.escape(self.SPECIAL_CHARS)}]", password))

        char_types = sum([has_lower, has_upper, has_digit, has_special])
        if char_types >= 3:
            score += 1
        if char_types >= 4:
            score += 1

        # Penalize common patterns
        if password.lower() in self.COMMON_PASSWORDS:
            score = max(0, score - 2)

        if self._has_obvious_sequential_chars(password) or self._has_repeated_chars(
            password
        ):
            score = max(0, score - 1)

        return min(4, score)

    def generate_password(self, length: int = 16) -> str:
        """
        Generate cryptographically secure password.

        Args:
            length: Desired password length

        Returns:
            Generated password meeting all requirements
        """
        if length < self.min_length:
            length = self.min_length

        # Ensure at least one character from each required set
        password_chars = []

        if self.require_uppercase:
            password_chars.append(secrets.choice(self.UPPERCASE_CHARS))
        if self.require_lowercase:
            password_chars.append(secrets.choice(self.LOWERCASE_CHARS))
        if self.require_digits:
            password_chars.append(secrets.choice(self.DIGIT_CHARS))
        if self.require_special_chars:
            password_chars.append(secrets.choice(self.SPECIAL_CHARS))

        # Fill remaining length with random characters from all sets
        all_chars = ""
        if self.require_uppercase:
            all_chars += self.UPPERCASE_CHARS
        if self.require_lowercase:
            all_chars += self.LOWERCASE_CHARS
        if self.require_digits:
            all_chars += self.DIGIT_CHARS
        if self.require_special_chars:
            all_chars += self.SPECIAL_CHARS

        remaining_length = length - len(password_chars)
        for _ in range(remaining_length):
            password_chars.append(secrets.choice(all_chars))

        # Shuffle to avoid predictable patterns
        secrets.SystemRandom().shuffle(password_chars)

        return "".join(password_chars)

    def add_to_password_history(self, user_id: str, password_hash: str) -> None:
        """
        Add password hash to user's history.

        Args:
            user_id: User identifier
            password_hash: Hashed password
        """
        if user_id not in self._password_histories:
            self._password_histories[user_id] = []

        history = self._password_histories[user_id]

        # Add new hash with timestamp
        history.append((password_hash, datetime.utcnow()))

        # Maintain history limit
        if len(history) > self.password_history_count:
            history.pop(0)  # Remove oldest

    def is_password_reused(self, user_id: str, password: str) -> bool:
        """
        Check if password was used recently.

        Args:
            user_id: User identifier
            password: Plain text password to check

        Returns:
            True if password was used recently
        """
        if user_id not in self._password_histories:
            return False

        history = self._password_histories[user_id]

        # Check against recent password hashes
        for password_hash, _ in history:
            try:
                if self.verify_password(password, password_hash):
                    return True
            except Exception:
                # Skip invalid hashes
                continue

        return False

    def get_password_history(self, user_id: str) -> List[Tuple[str, datetime]]:
        """
        Get password history for user.

        Args:
            user_id: User identifier

        Returns:
            List of (hash, timestamp) tuples
        """
        return self._password_histories.get(user_id, [])

    def clear_password_history(self, user_id: str) -> None:
        """
        Clear password history for user.

        Args:
            user_id: User identifier
        """
        if user_id in self._password_histories:
            del self._password_histories[user_id]

    def is_password_expired(self, user_id: str, password_set_date: datetime) -> bool:
        """
        Check if password has expired.

        Args:
            user_id: User identifier
            password_set_date: When password was set

        Returns:
            True if password is expired
        """
        if not password_set_date:
            return True  # No date means expired

        expiry_date = password_set_date + timedelta(days=self.max_password_age_days)
        return datetime.utcnow() > expiry_date

    def days_until_expiry(self, user_id: str, password_set_date: datetime) -> int:
        """
        Calculate days until password expires.

        Args:
            user_id: User identifier
            password_set_date: When password was set

        Returns:
            Days until expiry (negative if already expired)
        """
        if not password_set_date:
            return -1

        expiry_date = password_set_date + timedelta(days=self.max_password_age_days)
        days_left = (expiry_date - datetime.utcnow()).days

        return days_left

    def check_password_breach(self, password: str) -> bool:
        """
        Check if password exists in HaveIBeenPwned breach database.

        Args:
            password: Password to check

        Returns:
            True if password found in breaches

        Raises:
            Exception: If API request fails
        """
        # Create SHA-1 hash of password
        sha1_hash = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()

        # Use k-anonymity: send first 5 characters, get range of hashes
        prefix = sha1_hash[:5]
        suffix = sha1_hash[5:]

        try:
            response = requests.get(
                f"https://api.pwnedpasswords.com/range/{prefix}", timeout=5
            )
            response.raise_for_status()

            # Check if our suffix appears in the response
            for line in response.text.splitlines():
                if line.startswith(suffix):
                    return True

            return False

        except requests.RequestException as e:
            raise Exception(f"Failed to check password breach: {e}")

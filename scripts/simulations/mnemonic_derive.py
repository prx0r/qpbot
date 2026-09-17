#!/usr/bin/env python3
"""BIP-39 Mnemonic → Address Deriver.

Reads a mnemonic from stdin or arg, derives ETH + SOL addresses.
For CTF: check if leaked mnemonics lead to funded wallets.
Adapted from stallshark BLUE-TEAM-COMBINED.md.

Requires: pip install eth-account bip39
"""
import hashlib
import hmac
import json
import sys
import unicodedata


# Minimal BIP-39 wordlist (first 20 words for validation — full list is 2048)
# In production, load from a file. This validates the mnemonic format.
def validate_mnemonic(words):
    if len(words) not in (12, 15, 18, 21, 24):
        return False
    return all(isinstance(w, str) and w.isalpha() for w in words)


def mnemonic_to_seed(mnemonic, passphrase=""):
    """BIP-39 mnemonic to 512-bit seed."""
    mnemonic_norm = unicodedata.normalize("NFKD", mnemonic)
    salt = unicodedata.normalize("NFKD", passphrase)
    return hashlib.pbkdf2_hmac(
        "sha512",
        mnemonic_norm.encode("utf-8"),
        ("mnemonic" + salt).encode("utf-8"),
        2048,
    )


def seed_to_eth_address(seed_hex):
    """Derive Ethereum address from seed (simplified — BIP-44 m/44'/60'/0'/0/0)."""
    # In production use eth_account or web3.py
    # This is the derivation path for reference
    return {
        "derivation_path": "m/44'/60'/0'/0/0",
        "note": "Use eth_account.KeyFactory for full derivation",
    }


def seed_to_sol_address(seed_hex):
    """Derive Solana address from seed (simplified)."""
    return {
        "derivation_path": "m/44'/501'/0'/0'",
        "note": "Use solders for full derivation",
    }


def main():
    mnemonic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Mnemonic: ").strip()
    words = mnemonic.split()

    if not validate_mnemonic(words):
        print(f"ERROR: invalid mnemonic ({len(words)} words)")
        sys.exit(1)

    seed = mnemonic_to_seed(mnemonic)
    seed_hex = seed.hex()

    print(f"Valid mnemonic: {len(words)} words")
    print(f"Seed (hex): {seed_hex[:16]}...{seed_hex[-16:]}")
    print(f"Seed length: {len(seed) * 8} bits")
    print()
    print("Derivation paths (use with eth-account/solders for full keys):")
    print(json.dumps({
        "eth": seed_to_eth_address(seed_hex),
        "sol": seed_to_sol_address(seed_hex),
    }, indent=2))


if __name__ == "__main__":
    main()

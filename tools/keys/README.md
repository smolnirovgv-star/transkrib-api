# Transkrib License Keys - Production Batch

## Generated Keys Information

- **Date**: 2026-02-24 21:23:50
- **Total Keys**: 50
- **Format**: `TRSK-XXXX-XXXX-XXXX-XXXX`
- **Secret Key**: Production 64-byte cryptographic key (see `SECURITY_NOTE.md`)
- **HMAC Algorithm**: SHA256

## Files in This Directory

### `keys_2026-02-24_21-23-50.txt`
Contains 50 pre-generated license keys ready for distribution.

**Format**:
```
TRSK-AUCP-VFBZ-U5S6-U5KUEZM3
TRSK-TKQJ-CWDF-MVWV-IFOMOOYG
...
```

### `used.txt`
Tracks activated/distributed keys.

**Format**:
```
TRSK-XXXX-XXXX-XXXX-XXXX | 2026-02-24 | customer@example.com
```

## Key Validation Test Results ✅

5 random keys tested successfully:
- TRSK-AUCP-VFBZ-U5S6-U5KUEZM3 ✓
- TRSK-BA2S-OVVA-SUQQ-M574N2IB ✓
- TRSK-FXXL-IVZD-N4M3-HCX4KOQF ✓
- TRSK-22W7-DO6F-HJH2-XDXR5EMR ✓
- TRSK-M23F-YQZI-IEFN-SQZWEYGH ✓

All keys verified against production `SECRET_KEY`.

## Distribution Workflow

### Step 1: Select Unused Key
```bash
# View available keys
cat keys_2026-02-24_21-23-50.txt
```

### Step 2: Record Usage
When distributing a key to a customer, add to `used.txt`:
```
TRSK-AUCP-VFBZ-U5S6-U5KUEZM3 | 2026-02-24 | john.doe@example.com
```

### Step 3: Send to Customer
Via encrypted channel (see `SECURITY_NOTE.md`):
- License key
- Download link for installer
- SHA256 checksum
- Setup instructions

## Security Guidelines

🔒 **CRITICAL: Keep this directory secure!**

- ✅ Store in encrypted folder (BitLocker, VeraCrypt)
- ✅ Restricted access (admin only)
- ✅ Regular backups (encrypted)
- ❌ Never commit to public repositories
- ❌ Never send unencrypted via email
- ❌ Never share multiple keys at once

## Generate More Keys

If you need additional keys:

```bash
cd C:\Users\Admin\OneDrive\Desktop\Cursor\app\tools
python keygen.py --count 100 --output ./keys/batch2/
```

This creates a new batch without overwriting existing keys.

## Key Rotation

If `SECRET_KEY` is rotated (annual or security breach):

1. All existing keys become invalid
2. Generate new batch with new secret
3. Notify customers of migration
4. Archive old keys for reference

See `SECURITY_NOTE.md` for detailed rotation procedure.

---

**Keys Ready**: 50 unused keys
**Status**: ✅ Validated and production-ready
**Next Step**: Distribute to customers as needed

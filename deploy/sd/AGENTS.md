<!-- Parent: ../AGENTS.md -->

# SD personalization

## Purpose

Windows-side, fail-closed preparation of one verified ROSY OS image for one
Pinky Pro. The signed image remains device-neutral; this directory creates the
one-time per-card provisioning bundle.

## Safety rules

- Public device names are `rosy-pinky-xxxx`; immutable UUID, hardware serial,
  and DDS robot number remain separate identities.
- Never accept a Wi-Fi passphrase on a command line or write it to logs,
  receipts, exceptions, or the common image.
- Disk selection is by a freshly re-probed physical disk number, serial, size,
  and bus type. A drive letter is never sufficient.
- Tests and `-PlanOnly` must not invoke an image writer or alter physical media.
- An image write is MEDIA evidence only; it is not BOOT, DEVICE, or FLEET proof.

## Testing

```powershell
python -m pytest test/test_sd_personalization.py test/test_sd_writer_contract.py -q
```

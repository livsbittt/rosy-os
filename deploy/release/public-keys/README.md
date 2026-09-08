# Release trust anchors

No production key exists yet. Commit only the selected Ed25519 **public** key as
`<signing-key-id>.pem` after repository/release ownership is decided. Configure
`ROSY_RELEASE_KEY_ID` in the GitHub `release` environment and require approval on
that environment. The signing private key stays in the offline signing environment.
Do not generate a shared key automatically in CI or on a robot.

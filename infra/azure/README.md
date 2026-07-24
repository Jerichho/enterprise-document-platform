# Azure infrastructure sketches

These files are **documentation-grade** starting points for a manual deploy.
They do **not** run automatically in CI and should not be applied unless you accept Azure cost.

```bash
# Example only — review and edit parameters first
az deployment group create \
  --resource-group ekp-demo \
  --template-file main.bicep \
  --parameters @parameters.example.json
```

## Contents

| File | Purpose |
|------|---------|
| `main.bicep` | Outline: ACR, Log Analytics, Key Vault, storage, Postgres, Container Apps env |
| `parameters.example.json` | Placeholder parameter names (no secrets) |

## Before you deploy

1. Replace every `CHANGE_ME` value.
2. Confirm Flexible Server networking (private access preferred).
3. Store `SECRET_KEY`, DB password, Together key, and storage connection string in Key Vault.
4. Build/push images to ACR from the repo Dockerfiles.
5. Run `alembic upgrade head` against the new database.
6. Delete the resource group when the demo is finished if you do not need it.

See [docs/azure.md](../../docs/azure.md) for the full mapping and operational notes.

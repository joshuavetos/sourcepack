# nested-manifest-scope-leakage

The trusted root `package.json` has no `axios` dependency, while a nested worker manifest declares it. The proposed root-level `app.js` import must not treat package-local nested evidence as repository-wide support. The required result is an unsupported dependency failure.

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0](https://github.com/zlucasmenezes/cognite-cdf-mcp/compare/v0.1.1...v0.2.0) (2026-11-07)


### Features

* **mcp:** add get_access and report missing write access ([#14](https://github.com/zlucasmenezes/cognite-cdf-mcp/issues/14)) ([56a5788](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/56a578878c1ec17c31733feb850d609f71e10cca))
* **mcp:** respect CDF limits on instance search, query, and writes ([#8](https://github.com/zlucasmenezes/cognite-cdf-mcp/issues/8)) ([f766831](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/f76683156402091a578f20a28f786200793fe94a))


### Bug Fixes

* **mcp:** chunk spaces, show dry-run properties, and spell out replace ([#10](https://github.com/zlucasmenezes/cognite-cdf-mcp/issues/10)) ([c99ca5e](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/c99ca5ef6c2d96a2745cb6b2a86d4dc3f4efda32))
* **mcp:** mark get_filter_docs as closed-world ([5e2c0ac](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/5e2c0acbf819c2d8c7e3c466eb1905723a27024a))


### Documentation

* add AGENTS.md for MCP usage ([3d57279](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/3d57279c0f319cc6086e7601a434a56e6765527e))

## [0.1.1](https://github.com/zlucasmenezes/cognite-cdf-mcp/compare/v0.1.0...v0.1.1) (2026-11-05)


### Features

* **auth:** add CDF client credentials and token login ([4841d9c](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/4841d9cf74dbbdf463a686ac96bb0e44ec462d19))
* **cdf:** cache Cognite clients per environment session ([63e7945](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/63e794543c45c8a603163b92aea7a313387685c3))
* **config:** discover CDF_PROJECT_* environment aliases ([09066be](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/09066be477bd3df3b443b09740a5474faccc288f))
* **mcp:** add apply and delete instances tools with dry-run ([75b6523](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/75b6523ae0da169562ea2fd504d62c06ab3b7713))
* **mcp:** add apply and delete spaces tools with dry-run ([3c55ac9](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/3c55ac96d9d760bea9b3d7997853e5dabc9cedc2))
* **mcp:** add container list/get and filter docs tools ([941b775](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/941b775c2d445e96ebcfffe978fbea4a1e69c193))
* **mcp:** add cursor pagination to schema list tools ([842168e](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/842168e1ec09cd4e87841d610f177efb7a8d2f87))
* **mcp:** add DEFAULT_LIMIT and JSON filter/list param helpers ([913bd7c](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/913bd7c298eb009628751da416f10075a35c14d3))
* **mcp:** add delete_view tool with dry-run support ([da93b13](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/da93b1319fcf311928f360f2d82e4409f62850b6))
* **mcp:** add get_data_model and get_space tools ([ed73e71](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/ed73e71edc65cfebcdae7ef385aa74540faa3cfe))
* **mcp:** add inspect_instance tool for involved views/containers ([44aaa3e](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/44aaa3e481c02fc34cdf78aac114222faba04998))
* **mcp:** add instance get, query, search, and aggregate tools ([b5f928e](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/b5f928ec1409b1ffd07e771678ba8446aaa7c914))
* **mcp:** add list_environments and use_environment tools ([095c841](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/095c841f7509930631b3aa7e8a94776872153335))
* **mcp:** add list_views and get_view tools ([79ee0e5](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/79ee0e52cd277d9f052158740f9b02777de4949b))
* **mcp:** add tool titles and wire inspect plus list cursors ([11a76d9](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/11a76d983cfffc1e1eeba650b2779a18bfe34fb1))
* **mcp:** annotate tools with readOnly and destructive hints ([f54c91b](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/f54c91bf24e74e1818ffaac639c4d929a5ab158f))
* **mcp:** expose list_data_models and list_spaces tools ([c264589](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/c26458915a2df733a06af09fa959afcf2f3432ec))
* **mcp:** register instance and space tools on the server ([1c9d5eb](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/1c9d5eb7a272b17d29aedea2ac10201288bc6da8))
* **mcp:** register view and resource get tools on the server ([e3612e4](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/e3612e4cbb5fe84d93999bd95da169800c5495bc))
* **mcp:** return actionable NotFound hints from get tools ([d220c58](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/d220c58dd114075383dc914d1b7273839fdc9472))
* **mcp:** wire environment override across CDF tools ([92b1a33](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/92b1a3389d478b16469543b7085bb8d8e336bd1e))
* **safety:** default write tools to dry_run via DEFAULT_DRY_RUN ([0b5f046](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/0b5f04665c78bbf14a1bea361d4f77ba89ef82a9))


### Bug Fixes

* **mcp:** tighten delete_spaces input schema item types ([5b4654e](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/5b4654ecb0f80dc4a9534e6fb626e39aeddd1150))
* **mcp:** treat session environment tools as read-only ([#5](https://github.com/zlucasmenezes/cognite-cdf-mcp/issues/5)) ([c3e3bfa](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/c3e3bfa2b8e2f9016a76e539c8efb661fe8ec1b2))


### Documentation

* add contributing guide and release workflow notes ([a418c13](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/a418c13a8ccae47e3ba50e4b8256598d9da38bee))
* add MCP recipes and document inspect and list cursors ([d39a66c](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/d39a66c04f22389368964d93e4ff5fada842609f))
* add setup, auth, and Cursor MCP configuration ([fbe0743](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/fbe074303fe93bf45881e2f9ef2748877d0d34d7))
* add WIP disclaimer, uvx install, and anonymize examples ([7cfdfc3](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/7cfdfc3cdd0e2bc1786c8fb1d38512d9dbb20d4f))
* document delete_view and refresh tools layout ([5a2892e](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/5a2892eff51809d16ac1dad33e9ae125d05c3f08))
* document dry_run=true default for write tools ([64d188e](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/64d188e48925a3fb0864b2c7db038c0a7891bcaf))
* document flat multi-environment Cursor MCP config ([dee57bf](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/dee57bf2bb0730fdd61fd412c822b55eb2d49d9d))
* document instance and space MCP tools ([ef83bf9](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/ef83bf95b190441cfef3638e26b7af5506dc3766))
* document list and get tools for models, spaces, and views ([fd63de6](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/fd63de6dc8161086c739d61119617d0b73f395bb))
* document pytest and CI quality gates ([7cfee27](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/7cfee27169485d22a41fb1df43a35cac88f2f6f5))


### Miscellaneous Chores

* force next release to 0.1.1 ([#6](https://github.com/zlucasmenezes/cognite-cdf-mcp/issues/6)) ([5ff826a](https://github.com/zlucasmenezes/cognite-cdf-mcp/commit/5ff826ad1f808e21199304dbd0c4f0e13bfadb74))

## [0.1.0](https://github.com/zlucasmenezes/cognite-cdf-mcp/releases/tag/v0.1.0) (2026-11-04)

### Features

* First experimental MCP server for Cognite Data Fusion (schema/instance tools, multi-environment aliases, token auth).
* Write tools default to `dry_run=true` via `DEFAULT_DRY_RUN`.

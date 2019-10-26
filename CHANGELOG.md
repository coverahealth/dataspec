# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Add an exact length validator to the string spec factory (#2)
- Add conforming string formats (#3)
- Add ISO time string format (#4)
- Allow type-checking specs to be created by passing a type directly to `s` (#12)
- Add email address string format (#6)
- Add URL string format factory `s.url` (#16)
- Add Python `dateutil` support for parsing dates (#5)

### Changed
- `s.all` and `s.any` create `ValidatorSpec`s now rather than `PredicateSpec`s
  which yield richer error details from constituent Specs

### Fixed
- Guard against `inspect.signature` failures with Python builtins (#18)

## [0.1.0] - 2019-10-20
### Added
- Initial commit

# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Add `s.dict_tag` as a convenience factory for building mapping specs for which
  the value spec tags are derived automatically from the corresponding dict keys (#52)
- Add documentation built using Sphinx and hosted on ReadTheDocs (#9)

## [v0.2.5] - 2020-04-10
### Added
- Add `SpecPredicate` and `tag_maybe` to the public interface (#49)

### Fixed
- Predicates decorated by `pred_to_validator` will now properly be converted into
  validator specs (#54)
- Apply conformers for `s.inst`, `s.date`, `s.time`, `s.inst_str`, and `s.phone` after
  the default conformer, so conformers have access to the conformed object (#50)

## [v0.2.4] - 2019-12-19
### Added
- Add `s.blankable` Spec for specifying optional string values (#45)
- Add `s.default` Spec for specifying default values on failing Specs (#46)


## [v0.2.3] - 2019-11-27
### Fixed
- The default conformer for Specs created from `Enum` instances now accepts the
  `Enum.name` value in addition to the `Enum.value` and `Enum` singleton itself (#41)


## [v0.2.2] - 2019-11-27
### Added
- Allow `s.str`'s `regex` kwarg to be a pre-existing pattern returned from
  `re.compile` (#36)

### Fixed
- `s.any` now conforms values using the first successful Spec's conformer (#35)


## [v0.2.1] - 2019-10-28
### Fixed
- Allow regex repetition pattern (such as `\d{5}`) in error format string
  without throwing a spurious exception (#32)


## [v0.2.0] - 2019-10-28
### Added
- Add an exact length validator to the string spec factory (#2)
- Add conforming string formats (#3)
- Add ISO time string format (#4)
- Allow type-checking specs to be created by passing a type directly to `s` (#12)
- Add email address string format (#6)
- Add URL string format factory `s.url` (#16)
- Add Python `dateutil` support for parsing dates (#5)
- Add Python `phonenumbers` support for parsing international telephone numbers (#10)
- Add format string (`strptime`) support to date/time spec factories (#29)

### Changed
- `s.all` and `s.any` create `ValidatorSpec`s now rather than `PredicateSpec`s
  which yield richer error details from constituent Specs
- Add `bytes` exact length validation
- Converted the string `email` formatter into a full Spec factory as `s.email` (#27)

### Fixed
- Guard against `inspect.signature` failures with Python builtins (#18)
- `s.date`, `s.inst`, and `s.time` spec factory `before` and `after` must now
  agree (`before` must be strictly equal to or before `after`) (#25)

### Removed
- The string email address format checker from #6 (#27)


## [v0.1.post1] - 2019-10-20
### Added
- Initial commit


[v0.2.5]: https://github.com/coverahealth/dataspec/compare/v0.2.4..v0.2.5
[v0.2.4]: https://github.com/coverahealth/dataspec/compare/v0.2.3..v0.2.4
[v0.2.3]: https://github.com/coverahealth/dataspec/compare/v0.2.2..v0.2.3
[v0.2.2]: https://github.com/coverahealth/dataspec/compare/v0.2.1..v0.2.2
[v0.2.1]: https://github.com/coverahealth/dataspec/compare/v0.2.0..v0.2.1
[v0.2.0]: https://github.com/coverahealth/dataspec/compare/v0.1.post1..v0.2.0
[v0.1.post1]: https://github.com/coverahealth/dataspec/releases/tag/v0.1.post1

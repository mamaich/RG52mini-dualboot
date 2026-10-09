# Выпуск v1.1

*Заготовка: выпуск выходит вместе с dArkOS 1.1 — номер карты совпадает с
номером dArkOS в ней. Эта строка убирается при публикации.*

Одна SD-карта для **AISLPC RG52 Mini** (Rockchip RK3562) с двумя системами —
**GammaOS Next** (Android 14) и **dArkOS** (Debian) — и меню выбора при
включении. Здесь перечислено то, что изменилось после [v1.0](release-v1.0.md).

| | |
|---|---|
| Образ | *заполнить при выпуске* |
| sha256 образа | *заполнить при выпуске* |
| Карта | от 32 ГБ |
| GammaOS Next | *последняя на момент сборки* — [mamaich/GammaOSNext-RG52mini](https://github.com/mamaich/GammaOSNext-RG52mini) |
| dArkOS | 1.1 — [mamaich/dArkOS_rg52mini](https://github.com/mamaich/dArkOS_rg52mini) |
| Загрузчик | [rg52mini-1.4](https://github.com/mamaich/u-boot-rk3562-rg52mini/releases/tag/rg52mini-1.4) — [mamaich/u-boot-rk3562-rg52mini](https://github.com/mamaich/u-boot-rk3562-rg52mini) |

## Как записать

Как в [v1.0](release-v1.0.md#как-записать): все тома архива в одну папку,
распаковать первый, `.img` записать на карту от 32 ГБ.

## Что нового

*Заполняется по мере изменений: что нового в dArkOS 1.1 и в GammaOS, которая
войдёт в образ.*

## Подробности

Как устроена карта и почему именно так — [01-устройство.md](01-устройство.md).
Как собрать самому — [02-сборка.md](02-сборка.md).

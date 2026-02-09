# Application subsystem for plotting tide calendars with gnuplot  

## Quick Start
For help:
`tide_calendar2 -h`

## Manual:
[manual pdf](./doc/tide_calendar2_manual.pdf)

### updating the manual
1. edit [manual source doc](./doc/tide_calendar2_manual_0.1.doc)
1. export as pdf
1. Make examples with cookbook.ksh then concatentate ps and ps2pdf
1. Use adobe acrobat to insert/replace examples into manual

## Environment:
Tidal unit linux virtual machines - typically `ntcm`

Production (shared storage): 
* `/g/ns/ntc/op/dm/bin/tidecalendars2/`
Development (ntcm server): 
* `/home/james/bin/utilities/tidecalendars2/`


Assumed dependency versions
* gnuplot 4.2 patchlevel 6
* GMT4.5 utility minmax
* `tzdata` package used for daylight savings
* other unix standards...
* ps2pdf wrapper for gs

Script to "port" dev version to shared production location :
[./dev2ops.ksh](./dev2ops.ksh)

NOTE:
Do not edit the operational environment unless you really need to.
Make changes in the development environment, and then port across

## Previous version
`tidecalendar` (tbc)
That version makes different assumptions about tide file structure layout etc


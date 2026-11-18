<!-- Template: copy into the project folder, save as README.md (German version: PROJEKT_README.de.md as README.de.md) and replace the placeholders in angle brackets. -->

<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# <No.> <Project name>

<img src="../../docs/badges/status-en.svg" alt="Status: in progress">

<One or two sentences: what does the system do, and which problem does it solve? Example: a button at the material station reports a withdrawal, and an LED confirms it.>

![Setup](../../docs/img/<project>-setup.jpg)

## Goal

- <What should work at the end?>
- <How can I tell that it works?>

## Hardware

| Component | Qty | Note |
|---|---|---|
| Raspberry Pi 400 | 1 | |
| <Red LED> | <1> | <with 220 Ω series resistor> |
| <Push button> | <1> | <internal pull-up> |

## Pin mapping

| Component | GPIO (BCM) | Physical pin |
|---|---|---|
| <LED> | <GPIO17> | <11> |
| <Button> | <GPIO27> | <13> |
| GND | | <6> |

Wiring diagram: [schaltplan/<project>_schaltplan.png](schaltplan/<project>_schaltplan.png)

## Run it

```bash
cd projekte/<folder>
python3 main.py
```

## How it works

<Describe the flow in your own words: what does the program read, how does it decide, what happens next? A state diagram or flowchart helps.>

## Tests

| Test case | Expected | Result |
|---|---|---|
| <Press the button> | <LED lights up for 2 s> | ⬜ |
| <Button bounces> | <only one event> | ⬜ |

## Safety and security

- <Electrical: series resistor, 3.3 V, power off while rewiring>
- <Software: no passwords in code, validate input>

## What I learned

- <Most important takeaway>
- <What I would do differently next time>

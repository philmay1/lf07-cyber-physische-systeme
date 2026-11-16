<p align="center">
  <a href="README.md"><img src="docs/badges/lang-en.svg" alt="English"></a>
  <a href="README.de.md"><img src="docs/badges/lang-de.svg" alt="Deutsch"></a>
</p>

<p align="center">
  <img src="docs/img/banner-en.svg" alt="LF07 Cyber-Physical Systems" width="100%">
</p>

<p align="center">
  <img src="docs/badges/raspberry-pi.svg" alt="Raspberry Pi 400">
  <img src="docs/badges/python.svg" alt="Python 3">
  <img src="docs/badges/mqtt.svg" alt="MQTT Mosquitto">
  <img src="docs/badges/mariadb.svg" alt="MariaDB">
  <img src="docs/badges/status-en.svg" alt="Status: in progress">
</p>

<p align="center">
  Projects and exercises from learning field 7 of my retraining as an IT specialist for system integration (Fachinformatiker für Systemintegration, Germany).
</p>

## About this repository

A cyber-physical system (CPS) connects software to the physical world. Sensors measure something, such as temperature or a button press. A program evaluates the reading and makes a decision. Actuators carry out that decision, for example an LED, a servo or a display.

In this learning field I build systems like that step by step on a Raspberry Pi 400. It starts with a single LED and ends with the SENTINEL project, which combines access control, environmental monitoring and a customer acceptance test.

<p align="center">
  <img src="docs/img/raspberry-pi-400-kit.jpg" alt="Raspberry Pi 400 Personal Computer Kit" width="720"><br>
  <sub>Raspberry Pi 400 Personal Computer Kit, the hardware behind every project in this repo</sub>
  <!-- Add the image source or replace it with your own photo before making the repo public -->
</p>

## Contents

- [Hardware](#hardware)
- [Software and tools](#software-and-tools)
- [Repository layout](#repository-layout)
- [Projects](#projects)
- [Progress](#progress)
- [Quick start on the Pi](#quick-start-on-the-pi)
- [Safety and security](#safety-and-security)
- [About me](#about-me)

## Hardware

| Part | Details |
|---|---|
| Raspberry Pi 400 | Computer built into a keyboard, Broadcom BCM2711 quad core (1.8 GHz), 4 GB RAM, Wi-Fi, Bluetooth 5.0, Gigabit Ethernet |
| Ports | 40-pin GPIO header on the back, 2 × micro HDMI, USB 3.0 and 2.0, USB-C power |
| Starter kit | Mouse, USB-C power supply, micro HDMI cable, microSD card with Raspberry Pi OS, Beginner's Guide |
| Components | LEDs with series resistors, push buttons, DHT11, matrix keypad, servo, LCD, breadboard and jumper wires |

## Software and tools

| Area | Used for |
|---|---|
| Raspberry Pi OS | Operating system on the Pi |
| Python 3 with `gpiozero` | Driving GPIO: LEDs, buttons, servo |
| MQTT (Mosquitto, `paho-mqtt`) | JSON messages between devices |
| MariaDB | Storing sensor readings and access data |
| Argon2 | Hashing PINs and passwords |
| Git, GitHub, VS Code with Remote-SSH | Writing code on the PC, running it on the Pi, keeping every version |

## Repository layout

```text
lf07-cyber-physische-systeme/
├── README.md                 this page
├── README.de.md              German version
├── docs/
│   ├── badges/               badges as local SVG files
│   ├── img/                  banner, photos, screenshots
│   └── schaltplaene/         wiring diagrams
├── projekte/
│   ├── 01-sentinel-projektstart/
│   ├── 02-lokale-materialstation/
│   ├── 03-vernetzte-materialstation/
│   ├── 04-sicherheitsmodul-klimapruefraum/
│   ├── 05-lokale-zutrittskontrolle/
│   ├── 06-dynamische-zutrittskontrolle/
│   ├── 07-umweltueberwachung/
│   ├── 08-gesicherte-transportbox/
│   ├── 09-sentinel-release-readiness/
│   └── 10-sentinel-kundenabnahme/
└── vorlagen/
    ├── PROJECT_README.md     project template in English
    └── PROJEKT_README.de.md  project template in German
```

Folder names stay German because the course is taught in German. Each project folder gets its own README based on the [template](vorlagen/PROJECT_README.md): goal, wiring, pin mapping, how to run it, tests and what I learned.

## Projects

| No. | Project | Topic | Status |
|---|---|---|---|
| 01 | [SENTINEL kickoff](projekte/01-sentinel-projektstart/) | Safe LED circuit, GPIO output | ⬜ open |
| 02 | [Local material station](projekte/02-lokale-materialstation/) | Digital inputs, pull-up and pull-down, debouncing | ⬜ open |
| 03 | [Networked material station](projekte/03-vernetzte-materialstation/) | MQTT, JSON, topics | ⬜ open |
| 04 | [Safety module for a climate test room](projekte/04-sicherheitsmodul-klimapruefraum/) | Sensor selection, states, countdown | ⬜ open |
| 05 | [Local access control](projekte/05-lokale-zutrittskontrolle/) | Matrix keypad, PIN, PWM and servo | ⬜ open |
| 06 | [Dynamic access control](projekte/06-dynamische-zutrittskontrolle/) | MariaDB, Argon2 hashes | ⬜ open |
| 07 | [Environmental monitoring](projekte/07-umweltueberwachung/) | DHT11, telemetry, hysteresis | ⬜ open |
| 08 | [Secured transport box](projekte/08-gesicherte-transportbox/) | State machine, LCD, two-way MQTT | ⬜ open |
| 09 | [SENTINEL release readiness](projekte/09-sentinel-release-readiness/) | System test, threat analysis, FMEA | ⬜ open |
| 10 | [SENTINEL customer acceptance](projekte/10-sentinel-kundenabnahme/) | Acceptance, handover, presentation | ⬜ open |

Status: ⬜ open, 🟡 in progress, ✅ done

## Progress

The order follows the course agenda. How the topics split across days is my own estimate.

<details>
<summary><b>Week 1</b>: basics, inputs, networking, actuators</summary>

| Day | Topics | Done |
|---|---|---|
| 1 | Kickoff, CPS architecture and platform choice, electrical safety, safe LED circuit, setting up the Pi and GPIO | ⬜ |
| 2 | Digital inputs, defined idle levels, polling, event handling, debouncing | ⬜ |
| 3 | MQTT and M2M, IoT protocols, Industrial Internet, JSON and interface contracts | ⬜ |
| 4 | Sensor selection and personal safety, timing logic, states, countdown | ⬜ |
| 5 | Matrix keypad and PIN entry, PWM, servo, safe actuators | ⬜ |

</details>

<details>
<summary><b>Week 2</b>: data, security, acceptance</summary>

| Day | Topics | Done |
|---|---|---|
| 6 | MariaDB, SQL and data model, Argon2 hashing, secure configuration | ⬜ |
| 7 | DHT11 readings and plausibility checks, telemetry, persistence, hysteresis | ⬜ |
| 8 | State machines, transport logic, parallel LCD, two-way MQTT | ⬜ |
| 9 | DevOps, Git and system testing, threat analysis, FMEA and risk prioritisation | ⬜ |
| 10 | Acceptance, handover and customer presentation, final assessment, lessons learned | ⬜ |

</details>

## Quick start on the Pi

```bash
# Get the repo onto the Pi
git clone https://github.com/<username>/lf07-cyber-physische-systeme.git
cd lf07-cyber-physische-systeme

# Create a virtual environment and install packages
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run a project, for example the first one
python3 projekte/01-sentinel-projektstart/main.py
```

I write the code in VS Code on my PC and connect to the Pi over Remote-SSH. Every working state gets its own commit.

## Safety and security

- I disconnect the Pi from power before changing any wiring.
- GPIO pins only handle 3.3 V, so every LED gets a series resistor.
- Passwords, PINs, Wi-Fi credentials and tokens live in a `.env` file, which `.gitignore` keeps out of the repo.
- PINs are stored only as Argon2 hashes, never in plain text.

## About me

I am retraining as an IT specialist for system integration at GFN in Germany. This repo documents what I built hands-on in learning field 7.

<!-- Optional: add a link to your GitHub profile or LinkedIn -->

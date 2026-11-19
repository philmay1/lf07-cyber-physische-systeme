<a id="top"></a>

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
  <b>Sensors measure. Software decides. Actuators act.</b><br>
  Hands-on projects from learning field 7 of my retraining as an IT specialist for system integration.
</p>

<p align="center">
  <img src="docs/badges/progress-en.svg" alt="3 of 12 done (projects and exercises)">
</p>

<p align="center">
  <a href="#current-status">Current status</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#projects">Projects</a> ·
  <a href="#exercises">Exercises</a> ·
  <a href="#roadmap">Roadmap</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#safety-and-security">Safety</a>
</p>

---

> [!NOTE]
> This repo grows with the course. The ten SENTINEL projects live in `projekte/`, extra exercises in `uebungen/`. Every folder brings its own README, code and schematic. The progress bar counts both.

## At a glance

<table>
<tr>
<td width="55%" valign="top">

**What is a cyber-physical system?**

A cyber-physical system (CPS) connects software to the physical world. A temperature sensor reports 31 °C, the program compares that with a limit, and a fan switches on. The Raspberry Pi is the brain, the GPIO pins are its hands.

**What happens here?**

Ten projects in two weeks, from a single LED to SENTINEL: a networked system with PIN access control, environmental monitoring, a database and a customer acceptance test.

</td>
<td width="45%" valign="top">

<img src="docs/img/raspberry-pi-400-kit.jpg" alt="Raspberry Pi 400 Personal Computer Kit">
<!-- Add the image source or replace it with your own photo before making the repo public -->

</td>
</tr>
</table>

## Current status

<table>
<tr>
<td width="45%" valign="top">

<img src="uebungen/tag04-ampel-dimmen/schaltplan/ampel-dimmen_steckplatine.png" alt="Breadboard view of the dimmed traffic light with three LEDs on GPIO25, GPIO8 and GPIO7">

</td>
<td width="55%" valign="top">

**Recently finished, all built and tested on the Raspberry Pi 400**

- ✅ Exercise day 4: [Dimming the traffic light](uebungen/tag04-ampel-dimmen/). Red at 100 %, yellow at 60 %, green at 20 %, dimmed with PWM.
- ✅ Exercise day 3: [Pedestrian crossing](uebungen/tag03-fussgaengerampel/). Traffic light for cars and pedestrians with a request button. A buzzer ticks during pedestrian green as a signal for blind people.
- ✅ Project 01: [SENTINEL kickoff](projekte/01-sentinel-projektstart/). A status LED on GPIO25 blinks 1 s on, 2 s off.

**What I learned:** the GPIO number and the pin number are two different things. Every LED needs a series resistor. A button needs a pull-up and debouncing, and a transistor switches the buzzer because the pin should not drive it alone. PWM can dim an LED even though the pin only knows on and off.

**Next up:** Project 02 Local material station. A push button becomes an input, with pull-up and debouncing.

</td>
</tr>
</table>

## Architecture

The target picture for SENTINEL. Every project adds one building block. Green is already built.

```mermaid
flowchart LR
    subgraph sensors["Sensors"]
        direction TB
        S1["DHT11<br>temperature, humidity"]
        S2["Matrix keypad<br>PIN entry"]
        S3["Push button<br>material withdrawal"]
    end

    subgraph pi["Raspberry Pi 400"]
        P["Python app<br>gpiozero, state machine"]
    end

    subgraph actuators["Actuators"]
        direction TB
        A1["LED"]
        A2["Servo<br>door lock"]
        A3["LCD"]
    end

    subgraph net["Network"]
        direction TB
        B(("MQTT broker<br>Mosquitto"))
        C["Dashboard or<br>second device"]
        D[("MariaDB")]
    end

    sensors --> P
    P --> actuators
    P <-->|"JSON over MQTT"| B
    B <--> C
    P -->|"readings, access log"| D

    classDef done fill:#2ea043,stroke:#2ea043,color:#fff
    class A1,P done
```

### Example: access control as a state machine

This is how a PIN lock (project 05 and 06) behaves. Drawing the states first makes the code much easier to write and to test.

```mermaid
stateDiagram-v2
    state "Entering PIN" as EnteringPIN
    [*] --> Locked
    Locked --> EnteringPIN: key pressed
    EnteringPIN --> Checking: hash key pressed
    EnteringPIN --> Locked: timeout 10 s
    Checking --> Open: PIN correct
    Checking --> Locked: PIN wrong
    Checking --> Alarm: 3rd wrong attempt
    Open --> Locked: after 5 s
    Alarm --> Locked: reset by admin
```

<p align="right"><a href="#top">back to top ↑</a></p>

## Projects

| No. | Project | What it does | Key skills | Status |
|:-:|---|---|---|:-:|
| 01 | [SENTINEL kickoff](projekte/01-sentinel-projektstart/) | Lights an LED safely through a GPIO pin | Series resistor, GPIO output | ✅ |
| 02 | Local material station | Registers withdrawals with a button | Pull-up, debouncing, events | ⬜ |
| 03 | Networked material station | Sends every withdrawal as an MQTT message | MQTT, JSON, topics | ⬜ |
| 04 | Safety module for a climate test room | Warns before anyone enters an unsafe room | Sensor choice, countdown | ⬜ |
| 05 | Local access control | Opens a lock after the right PIN | Keypad, PWM, servo | ⬜ |
| 06 | Dynamic access control | Checks PINs against a database | MariaDB, Argon2 | ⬜ |
| 07 | Environmental monitoring | Logs climate data and reacts to limits | DHT11, hysteresis | ⬜ |
| 08 | Secured transport box | Tracks the box state and reports it | State machine, LCD | ⬜ |
| 09 | SENTINEL release readiness | Tests the whole system and rates its risks | System test, FMEA | ⬜ |
| 10 | SENTINEL customer acceptance | Hands the system over to the "customer" | Acceptance, presentation | ⬜ |

<sub>⬜ open · 🟡 in progress · ✅ done</sub>

## Exercises

Extra tasks from class and the Raspberry Pi Beginner's Guide. They are not part of SENTINEL but count towards the progress bar.

| Day | Exercise | What it does | Key skills | Status |
|:-:|---|---|---|:-:|
| 03 | [Pedestrian crossing](uebungen/tag03-fussgaengerampel/) | Car and pedestrian lights with a request button and a ticking signal | Pull-up, debouncing, events, PNP transistor | ✅ |
| 04 | [Dimming the traffic light](uebungen/tag04-ampel-dimmen/) | Lights the traffic light at three levels: red 100 %, yellow 60 %, green 20 % | PWM, duty cycle, PWMLED | ✅ |

<details>
<summary><b>Planned MQTT topics</b> (draft, will change with project 03)</summary>

| Topic | Direction | Example payload |
|---|---|---|
| `sentinel/station1/material` | Pi → broker | `{"item": "M3 screws", "action": "taken", "ts": "2026-11-18T09:15:00Z"}` |
| `sentinel/room1/climate` | Pi → broker | `{"temp_c": 22.4, "humidity": 48}` |
| `sentinel/door1/state` | Pi → broker | `{"state": "locked"}` |
| `sentinel/door1/command` | broker → Pi | `{"cmd": "unlock", "by": "admin"}` |

</details>

## Roadmap

Planned schedule for the two course weeks.[^1]

```mermaid
timeline
    title LF07 in ten course days
    section Week 1
        Day 1 : Basics, LED, GPIO ✅
        Day 2 : Inputs and debouncing
        Day 3 : MQTT and IoT protocols
        Day 4 : Sensors and timing logic
        Day 5 : Keypad, PWM, servo
    section Week 2
        Day 6 : MariaDB and Argon2
        Day 7 : DHT11 and telemetry
        Day 8 : State machines and LCD
        Day 9 : DevOps, security, FMEA
        Day 10 : Acceptance and assessment
```

### What I will be able to do after LF07

- [ ] Wire LEDs, buttons and sensors safely to the GPIO header
- [ ] Read inputs reliably with pull-up resistors and debouncing
- [ ] Connect devices over MQTT with a clear JSON interface
- [ ] Store sensor data and hashed PINs in MariaDB
- [ ] Model behaviour as a state machine
- [ ] Assess risks with a threat analysis and an FMEA
- [ ] Present and hand over a system to a customer

<p align="right"><a href="#top">back to top ↑</a></p>

## Hardware

| Part | Details |
|---|---|
| Raspberry Pi 400 | Computer built into a keyboard, Broadcom BCM2711 quad core (1.8 GHz), 4 GB RAM, Wi-Fi, Bluetooth 5.0, Gigabit Ethernet |
| Ports | 40-pin GPIO header on the back, 2 × micro HDMI, USB 3.0 and 2.0, USB-C power |
| Starter kit | Mouse, USB-C power supply, micro HDMI cable, microSD card with Raspberry Pi OS, Beginner's Guide |
| Components | LEDs with series resistors, push buttons, DHT11, matrix keypad, servo, LCD, breadboard and jumper wires |

> [!TIP]
> Run `pinout` in the Pi's terminal. It prints a map of all 40 GPIO pins, which saves a lot of counting.

## Repository layout

```text
.
├── projekte/                     SENTINEL projects 01 to 10
│   └── 01-sentinel-projektstart/
│       ├── README.md, README.de.md
│       ├── main.py
│       └── schaltplan/           Fritzing file (.fzz) and images
├── uebungen/                     exercises from class and the guide
│   └── tag03-fussgaengerampel/   same layout as a project
├── docs/                         banner, images and badges for the README
├── .github/vorlagen/             README templates for new projects
└── requirements.txt
```

## Quick start

```bash
# Get the repo onto the Pi
git clone https://github.com/philmay1/lf07-cyber-physische-systeme.git
cd lf07-cyber-physische-systeme

# Create a virtual environment and install packages
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run a project, for example the first one
python3 projekte/01-sentinel-projektstart/main.py

# Or the pedestrian crossing
python3 uebungen/tag03-fussgaengerampel/ampel.py
```

<details>
<summary><b>My workflow: PC, GitHub and Pi</b></summary>

```mermaid
sequenceDiagram
    participant PC as VS Code on my PC
    participant GH as GitHub
    participant Pi as Raspberry Pi 400
    PC->>Pi: edit and run code over Remote-SSH
    Pi-->>PC: output, errors
    PC->>GH: commit and push
    GH->>Pi: git pull on a second Pi or after a reset
```

Useful shortcuts in VS Code: <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>P</kbd> opens the command palette, <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>G</kbd> opens source control.

</details>

## Safety and security

> [!WARNING]
> GPIO pins work with 3.3 V. Connecting 5 V to an input pin can destroy the Pi. Every LED needs a series resistor, and the Pi stays unplugged while I change the wiring.

> [!IMPORTANT]
> Passwords, PINs, Wi-Fi credentials and tokens never go into the code. They live in a `.env` file that `.gitignore` keeps out of the repo, and PINs are stored only as Argon2 hashes.

## About me

I am retraining as an IT specialist for system integration at GFN in Germany. This repo documents what I built hands-on in learning field 7.

<!-- Optional: add a link to your GitHub profile or LinkedIn -->

<p align="right"><a href="#top">back to top ↑</a></p>

[^1]: The order follows the official course agenda. The split across days is my own estimate.

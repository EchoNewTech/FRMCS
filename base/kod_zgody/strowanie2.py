import asyncio
import sys

try:
    import msvcrt


    def getch():
        return msvcrt.getch().decode('utf-8', 'ignore').lower()
except ImportError:
    import tty
    import termios


    def getch():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch.lower()

async def safety_monitor(express, cargo):
    LOOP_LEN = 400 # TODO wirtualna dł trasy {cm}
    SAFE_DIST = 40 # TODO bezpieczny odstep {cm}
    counter = 0

    while True:
        # aktualizacja pozycji
        p_express = express.update_position(LOOP_LEN)
        p_cargo = cargo.update_position(LOOP_LEN)

        # obl dystansu od tyłu pociągu
        dist_express = (p_express - p_cargo) % LOOP_LEN
        dist_cargo = (p_cargo - p_express) % LOOP_LEN

        counter += 1
        # jeżeli pociągi są za blisko
        if dist_express < SAFE_DIST and cargo.speed > 0:
            print(f"\n Pociąg Cargo zbyt blisko Express (Dystans: {dist_express:.0f})")
            await cargo.stop()

        if dist_cargo < SAFE_DIST and express.speed > 0:
            print(f"\n Pociąg Cargo zbyt blisko Express (Dystans: {dist_cargo:.0f})")
            await express.stop()
        
        await asyncio.sleep(0.1) # sprawdzaj 10 razy na sekundę

async def control_loop(express, cargo):
    """Główna pętla obsługująca sterowanie oboma pociągami"""
    asyncio.create_task(safety_monitor(express, cargo))
    SPEED_STEP = 10

    print("\n" + "=" * 30)
    print("Express:")
    print("  W - Przyspiesz")
    print("  S - Zwolnij / Cofaj")
    print("  A - Zatrzymaj")
    print("  D - Steruj światłami")
    print("-" * 30)
    print("Cargo:")
    print("  U - Przyspiesz")
    print("  J - Zwolnij / Cofaj")
    print("  H - Zatrzymaj")
    print("-" * 30)
    print("  x - WYJŚCIE")
    print("=" * 30)

    while True:
        cmd = await asyncio.to_thread(getch)
        # === ZAKOŃCZENIE ===
        if cmd == "x":
            print("\nZamykanie aplikacji...")
            break
        # === EXPRESS ===
        elif cmd == "w" and express.client and express.client.is_connected:
            await express.send_speed(express.speed + SPEED_STEP)
            print(f"Express prędkość: {express.speed}%")

        elif cmd == "s" and express.client and express.client.is_connected:
            await express.send_speed(express.speed - SPEED_STEP)
            print(f"Express prędkość: {express.speed}%")

        elif cmd == "a" and express.client and express.client.is_connected:
            await express.stop()
            print("Express ZATRZYMANY")

        elif cmd == "d" and express.client and express.client.is_connected:
            if express.light_on:
                await express.set_light(0)
                print("Express: Światła WYŁĄCZONE")
            else:
                await express.set_light(100)
                print("Express: Światła WŁĄCZONE")
        # === CARGO ===
        elif cmd == "u" and cargo.client and cargo.client.is_connected:
            await cargo.send_speed(cargo.speed + SPEED_STEP)
            print(f"Cargo prędkość: {cargo.speed}%")

        elif cmd == "j" and cargo.client and cargo.client.is_connected:
            await cargo.send_speed(cargo.speed - SPEED_STEP)
            print(f"Cargo prędkość: {cargo.speed}%")

        elif cmd == "h" and cargo.client and cargo.client.is_connected:
            await cargo.stop()
            print("Cargo ZATRZYMANY")
# ha-electricity-price
Sensor showing the total electricity price based on raw price sensor and taxes and fees fetched from the [Eloverblik](https://eloverblik.dk/) API.
This will create a sensor with similar information and layout as the sensor created by the [Nordpool custom integration](https://github.com/custom-components/nordpool/), which in most cases allows it to be used in place of the Nordpool sensor, when you want to know the actual price you pay, not just the raw electricity price (which in many cases is only a small fraction of the total price).  

## REQUIREMENTS
1. The "Nordpool" custom integration set up (https://github.com/custom-components/nordpool/).
2. An API TOKEN and your metering point from Eloverblik (get here: https://eloverblik.dk/).

## NOTE
As of November 2024, the underlying [pyeloverblik](https://github.com/JonasPed/pyeloverblik) is outdated.
I have submitted a pull request to the owner. In the meantime, you can manually patch the installed version by making the changes suggested in [this comment](https://github.com/JonasPed/pyeloverblik/issues/26).


## INSTALLATION
### HACS Installation (Recommended)

This Integration is not part of the default HACS store, but you can add it as a Custom repository in HACS by doing the following:

    Go to HACS in your HA installation, and click on Integrations
    Click the three vertical dots in the upper right corner, and select Custom repositories
    Add https://github.com/Aephir/ha-electricity-price and select Integration as Category, and then click Add

You should now be able to find this Integration in HACS. (Most times you need to do a Hard Refresh of the browser before it shows up)

### Manual Installation

To add ha-electricity-price to your installation, create this folder structure in your /config directory:

custom_components/ha-electricity-price. Then, drop the content of `https://github.com/Aephir/ha-electricity-price/tree/main/custom_components/electricity_price` into that folder.

## CONFIGURATION

In order to add this Integration to Home Assistant, go to Settings and Integrations. If you just installed ha-electricity-price, do a Hard Refresh in your browser, while on this page, to ensure the Integration shows up.

Now click the + button in the lower right corner, and then search for "Electricity Price". That should bring up the below screen:

<img width="387" alt="Screenshot 2024-11-30 at 16 05 40" src="https://github.com/user-attachments/assets/1b440994-327f-46b3-bebd-d87f8ba1661a">

Insert the entity_id of the Nordpool sensor, e.g., `sensor.nordpool_kwh_dk2_dkk_3_10_0` and click "Submit" to get to this screen:

<img width="387" alt="Screenshot 2024-11-30 at 16 05 59" src="https://github.com/user-attachments/assets/c245e8d1-bbb5-47ca-92e2-f0747d99d4f3">

Here you need to enter the API key generated at https://eloverblik.dk/ and your metering point, which can also be found there.
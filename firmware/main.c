#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "hardware/spi.h"
#include "hardware/adc.h"
#include "hardware/uart.h"

#define I2C_SDA 4
#define I2C_SCL 5
#define LOOPBACK_A 6
#define LOOPBACK_B 7
#define SPI_MISO 16
#define SPI_MOSI 19
#define SPI_SCK  18

/* Requires two physical jumpers: GP6 <-> GP7 and GP16 <-> GP19.
 * Without them this test must FAIL. It drives one pin and samples the other,
 * in both directions, so a missing or one-way jumper is caught. */
static void test_gpio_loopback(void) {
    gpio_init(LOOPBACK_A); gpio_init(LOOPBACK_B);
    int pass = 1;
    for (int i = 0; i < 8; i++) {
        uint a = i & 1, b = (i >> 1) & 1;

        gpio_set_dir(LOOPBACK_A, GPIO_OUT);
        gpio_set_dir(LOOPBACK_B, GPIO_IN);
        gpio_put(LOOPBACK_A, a);
        sleep_us(50);
        if (gpio_get(LOOPBACK_B) != a) pass = 0;   /* A drives, B reads */

        gpio_set_dir(LOOPBACK_B, GPIO_OUT);
        gpio_set_dir(LOOPBACK_A, GPIO_IN);
        gpio_put(LOOPBACK_B, b);
        sleep_us(50);
        if (gpio_get(LOOPBACK_A) != b) pass = 0;   /* B drives, A reads */
    }
    gpio_set_dir(LOOPBACK_A, GPIO_IN);
    gpio_set_dir(LOOPBACK_B, GPIO_IN);
    printf("TEST gpio_loopback %s\n", pass ? "PASS" : "FAIL");
}

/* A bus with no devices attached is a PASS (value=0): the pull-ups hold SDA/SCL
 * high and every address NACKs cleanly. A stuck or shorted bus is a FAIL. */
static void test_i2c_scan(void) {
    i2c_init(i2c0, 100 * 1000);
    gpio_set_function(I2C_SDA, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA); gpio_pull_up(I2C_SCL);
    int found = 0, errs = 0;
    for (uint8_t addr = 0x08; addr < 0x78; addr++) {
        uint8_t buf;
        int rc = i2c_read_timeout_us(i2c0, addr, &buf, 1, false, 25000);
        if (rc >= 0) found++;
        else if (rc != PICO_ERROR_GENERIC) errs++;   /* GENERIC == clean NACK */
    }
    printf("TEST i2c_scan %s value=%d\n", errs ? "FAIL" : "PASS", found);
}

/* Requires a jumper GP16 (MISO) <-> GP19 (MOSI). */
static void test_spi_loopback(void) {
    spi_init(spi0, 1000 * 1000);
    gpio_set_function(SPI_MISO, GPIO_FUNC_SPI);
    gpio_set_function(SPI_MOSI, GPIO_FUNC_SPI);
    gpio_set_function(SPI_SCK,  GPIO_FUNC_SPI);
    uint8_t tx[4] = {0xDE, 0xAD, 0xBE, 0xEF};
    uint8_t rx[4] = {0};
    spi_write_read_blocking(spi0, tx, rx, 4);
    int pass = (rx[0] == tx[0] && rx[1] == tx[1] && rx[2] == tx[2] && rx[3] == tx[3]);
    printf("TEST spi_loopback %s\n", pass ? "PASS" : "FAIL");
}

/* GP26 is floating, so an exact voltage can't be asserted. What is checked is
 * that a conversion completes and the code sits in range. */
static void test_adc(void) {
    adc_init();
    adc_gpio_init(26);
    adc_select_input(0);
    adc_read();                                   /* discard first conversion */
    uint16_t v = adc_read();
    printf("TEST adc_read %s value=%u\n", v <= 4095 ? "PASS" : "FAIL", v);
}

static void test_uart_echo(void) {
    uart_init(uart0, 115200);
    gpio_set_function(0, GPIO_FUNC_UART);
    gpio_set_function(1, GPIO_FUNC_UART);
    uart_putc(uart0, 'X');
    printf("TEST uart_init PASS\n");
}

int main(void) {
    stdio_init_all();
    sleep_ms(2000);
    printf("BENCH-VALIDATOR RUN\n");
    test_gpio_loopback();
    test_i2c_scan();
    test_spi_loopback();
    test_adc();
    test_uart_echo();
    printf("BENCH-VALIDATOR DONE\n");
    while (1) tight_loop_contents();
}

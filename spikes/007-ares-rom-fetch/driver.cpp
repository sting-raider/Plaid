/* SPDX-License-Identifier: ISC
 * Original source-aware bounded observer; upstream code remains separate.
 */
#define PLAID_PHYSICAL_FETCH 1
#define PLAID_ROM_FETCH_SOURCE 1
#include "../006-ares-rom-source/driver.cpp"
#include "../004-ares-fetch/driver.cpp"
int main(int argc, char** argv) { return fetch_observer_main(argc, argv); }

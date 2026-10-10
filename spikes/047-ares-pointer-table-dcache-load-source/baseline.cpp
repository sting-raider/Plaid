/* SPDX-License-Identifier: ISC */
#define PLAID_TABLE_LOAD_SENSOR 0
#define main plaid_table_load_fixture_main
#include "driver.cpp"
#undef main
int main(int argc, char** argv) { return plaid_table_load_fixture_main(argc, argv); }

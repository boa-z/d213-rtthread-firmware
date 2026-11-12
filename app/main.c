/* SPDX-License-Identifier: Apache-2.0
 * Copyright (c) 2026 boa-z
 */
#include <rtthread.h>
#include <finsh.h>
#include "firmware_version.h"

static void fw_info(void)
{
    rt_kprintf("d213-rtthread-firmware %s\nproject: %s\nBSP: %s\nprofile: minimal\nconfig: %s\n",
               FW_VERSION, FW_COMMIT, FW_BSP_COMMIT, FW_CONFIG_HASH);
}
MSH_CMD_EXPORT(fw_info, Show firmware provenance);

int main(void)
{
    rt_kprintf("Hello from ArtInChip D213 minimal RT-Thread!\n");
    fw_info();
    return 0;
}

/****************************************************************************

   Thorlabs PAX Driver Sample Application

   Source file

   Date:          Sep-03-2015
   Software-Nr:   N/A
   Version:       0.0.1
   Copyright:     Copyright(c) 2015, Thorlabs GmbH (www.thorlabs.com)
   Author:        Thomas Schlosser (tschlosser@thorlabs.com)

   Changelog:     Sep-03-2015 - began

   Disclaimer:

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA


   How to setup the compiler project
   =================================

   1. Requirements:
      +  Thorlabs PAX Series VISA Instrument Driver installed.
            After installation the driver files can be found in
            "$(VXIPNPPATH)WinNT\"
            This is typically 'C:\VXIPNP\WinNT\' or
            'C:\Program Files\IVI Foundation\VISA\WinNT\'
      +  National Instruments VISA installed (V4.0 or higher)

   2. Create a new project in your IDE.

   3. Add the following files to the project:
      +  sample.c
      +  TLPAX.h

   4. The IDE needs to be pointed to these .LIB files:
      +  TLPAX_32.lib
      +  visa32.lib
      Some IDEs need the .LIB files added to the project. Others require
      different steps. Please refer to your compiler manual.

   5. Depending on your compiler you may need to set your compiler include
      search path to the VXIPNP include directory.
      This is typically 'C:\VXIPNP\WinNT\include' or
      'C:\Program Files\IVI Foundation\VISA\WinNT\include'

   6. Project settings in Microsoft Visual Studio C++:
      To use the Thorlabs PAX Series VISA Instrument Driver successfully
      in a Visual C++ project some paths and dependencies have to be included
      in the Project settings (both, in Debug and in Release configuration).
      +  Configuration > C/C++ > General settings: Additional include
         directories: "$(VXIPNPPATH)WinNT\include"
      +  Configuration > Linker > General settings: Additional library
         directories: "$(VXIPNPPATH)WinNT\lib\msc"
      +  Configuration > Linker > Input: Additional dependencies:
         "TLPAX_32.lib visa32.lib"


****************************************************************************/
	 
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <visa.h>
#include "TLPAX.h"  

/*===========================================================================
 Type definitions
===========================================================================*/

/*===========================================================================
 Macros
===========================================================================*/

#define TIMEOUT_MILLISEC   5000  // Communication timeout [ms]
#define NUM_MULTI_READING  1000

#define PI_VAL   (3.1415926535897932384626433832795f)  

/*===========================================================================
 Prototypes
===========================================================================*/
ViStatus find_instrument(ViChar **resource);
void error_exit(ViSession instrHdl, ViStatus err);
void waitKeypress(void);

ViStatus get_device_id(ViSession ihdl);

ViStatus get_measurement_mode(ViSession ihdl);
ViStatus set_measurement_mode(ViSession ihdl);
ViStatus get_basic_scan_rate(ViSession ihdl);
ViStatus set_basic_scan_rate(ViSession ihdl);
ViStatus get_power_range(ViSession ihdl);
ViStatus set_power_range(ViSession ihdl);
ViStatus get_scan(ViSession ihdl);			  

/*=============================================
 Functions
===========================================================================*/
int main(int argc, char **argv)
{
   ViStatus    err;
   ViChar      *rscPtr;
   ViSession   instrHdl = VI_NULL;
   int         c, done;

   printf("---------------------------------------------------\n");
   printf(" Thorlabs PAX Driver Sample Application\n");
   printf("---------------------------------------------------\n\n");

   // Parameter checking / Resource scanning
   if(argc < 2)
   {
      // Find resources
      err = find_instrument(&rscPtr);
      if(err) error_exit(VI_NULL, err);
      if(rscPtr == NULL) exit(EXIT_SUCCESS); // No instrument found
   }
   else
   {
      // Got resource in command line
      rscPtr = argv[1];
   }

   // Open session to PAX series instrument
   printf("Opening session to '%s' ...\n\n", rscPtr);
   err = TLPAX_init(rscPtr, VI_OFF, VI_ON, &instrHdl);
   if(err) error_exit(instrHdl, err);

   // Operations
   done = 0;
   do
   {
      printf("Operations:\n\n");
      printf("I: Read instrument information\n");
      printf("m: Get measurement mode\n");
      printf("M: Set measurement mode\n");
      printf("r: Get basic scan rate\n");
      printf("R: Set basic scan rate\n");
      printf("p: Get input power range\n");
      printf("P: Set input power range\n");
      printf("s: Get scan data set\n");
      printf("Q: Quit\n");
      printf("\n");

      printf("\nPlease select: ");
      while((c = getchar()) == EOF);
      fflush(stdin);
      printf("\n");

      switch(c)
      {
         case 'i':
         case 'I':
            if((err = get_device_id(instrHdl))) error_exit(instrHdl, err);
            break;

         case 'm':
            if((err = get_measurement_mode(instrHdl))) error_exit(instrHdl, err);
            break;

         case 'M':
            if((err = set_measurement_mode(instrHdl))) error_exit(instrHdl, err);
            break;

         case 'r':
            if((err = get_basic_scan_rate(instrHdl))) error_exit(instrHdl, err);
            break;

         case 'R':
            if((err = set_basic_scan_rate(instrHdl))) error_exit(instrHdl, err);
            break;
			
         case 'p':
            if((err = get_power_range(instrHdl))) error_exit(instrHdl, err);
            break;

         case 'P':
            if((err = set_power_range(instrHdl))) error_exit(instrHdl, err);
            break;

         case 's':
            if((err = get_scan(instrHdl))) error_exit(instrHdl, err);
            break;

         case 'q':
         case 'Q':
            done = 1;
            if(instrHdl != VI_NULL) TLPAX_close(instrHdl);
            break;

         default:
            printf("Invalid selection\n\n");
            break;
      }
   } while(!done);

   return VI_SUCCESS;
}

/*---------------------------------------------------------------------------
  Exit with error message
---------------------------------------------------------------------------*/
void error_exit(ViSession instrHdl, ViStatus err)
{
   ViChar buf[TLPAX_ERR_DESCR_BUFFER_SIZE];

   // Print error
   TLPAX_errorMessage (instrHdl, err, buf);
   fprintf(stderr, "ERROR: %s\n", buf);
   
   // Close instrument hande if open
   if(instrHdl != VI_NULL) TLPAX_close(instrHdl);
   
   // Exit program
   waitKeypress();
   exit (EXIT_FAILURE);
}  

/*---------------------------------------------------------------------------
  Print keypress message and wait
---------------------------------------------------------------------------*/
void waitKeypress(void)
{
   printf("Press <ENTER> to exit\n");
   while(getchar() == EOF);
}  

/*---------------------------------------------------------------------------
  Find Instrument

  List a menu of all supported devices connected to the system for user
  selection. If only one compatible device is connected it is immediately
  selected without showing the menu.

  Parameters:
  resource  Receives the pointer to a resource string to initiate a session
            to the selected device. The buffer is valid until the next call
            of find_instrument()

  Return value:   Error code if no resource string could be generated (e.g.
                  no device was detected on the system).
---------------------------------------------------------------------------*/
#define COMM_TIMEOUT    500
ViStatus find_instrument(ViChar **resource)
{
   ViStatus       err;
   static ViChar  rscBuf[TLPAX_BUFFER_SIZE];
   ViChar         name[TLPAX_BUFFER_SIZE], sernr[TLPAX_BUFFER_SIZE];
   ViUInt32       i, done, cnt, findCnt;
   ViBoolean      devAvailable;

   printf("Scanning for instruments ...\n");

   *resource = NULL;

   err = TLPAX_findRsrc(0, &findCnt);
   if(err) return err;

   if(findCnt < 1)
   {
      printf("No matching instruments found\n\n");
      return VI_ERROR_RSRC_NFOUND;
   }

   if(findCnt < 2)
   {
      // Found only one matching instrument - return this
      i = 0;
   }
   else
   {
      // Display selection
      done = 0;
      do
      {
         printf("Found %d matching instruments:\n\n", findCnt);

         // List found instruments
         for(cnt = 0; cnt < findCnt; cnt++)
         {
            // Print out menu
            err = TLPAX_getRsrcInfo(0, cnt, name, sernr, VI_NULL, &devAvailable);
            if(!err) printf("% d: %s \tS/N:%s\n", cnt+1, name, sernr);
         }

         printf("\nPlease select: ");
         while((i = getchar()) == EOF);
         i -= '0';
         fflush(stdin);
         printf("\n");
         if((i < 1) || (i > cnt))
         {
            printf("Invalid selection\n\n");
         }
         else
         {
            done = 1;
         }
      }
      while(!done);
   }

   // Copy resource string to static buffer
   err = TLPAX_getRsrcName (0, i, rscBuf);
   if(!err) *resource = rscBuf;
   return err;
} 

/*===========================================================================
 GET ID
===========================================================================*/
ViStatus get_device_id(ViSession ihdl)
{
   ViStatus err;
   ViChar   nameBuf[TLPAX_BUFFER_SIZE];
   ViChar   snBuf[TLPAX_BUFFER_SIZE];
   ViChar   revBuf[TLPAX_BUFFER_SIZE];

   err = TLPAX_identificationQuery (ihdl, VI_NULL, nameBuf, snBuf, revBuf);
   if(err) return err;
   printf("Instrument:    %s\n", nameBuf);
   printf("Serial number: %s\n", snBuf);
   printf("Firmware:      V%s\n", revBuf);
   if((err = TLPAX_revisionQuery (ihdl, revBuf, VI_NULL))) return err;
   printf("Driver:        V%s\n", revBuf);

   return VI_SUCCESS;
}

char const *get_measurement_mode_label(ViUInt32 mode)
{
   char const *str;

   switch(mode)
   {
      case TLPAX_MEASMODE_IDLE:        str = "Idle, no measurements are taken";                          break;
      case TLPAX_MEASMODE_HALF_512:    str = "0.5 revolutions for one measurement, 512 points for FFT";  break;
      case TLPAX_MEASMODE_HALF_1024:   str = "0.5 revolutions for one measurement, 1024 points for FFT"; break;
      case TLPAX_MEASMODE_HALF_2048:   str = "0.5 revolutions for one measurement, 2048 points for FFT"; break;
      case TLPAX_MEASMODE_FULL_512:    str = "1 revolution for one measurement, 512 points for FFT";     break;
      case TLPAX_MEASMODE_FULL_1024:   str = "1 revolution for one measurement, 1024 points for FFT";    break;
      case TLPAX_MEASMODE_FULL_2048:   str = "1 revolution for one measurement, 2048 points for FFT";    break;
      case TLPAX_MEASMODE_DOUBLE_512:  str = "2 revolutions for one measurement, 512 points for FFT";    break;
      case TLPAX_MEASMODE_DOUBLE_1024: str = "2 revolutions for one measurement, 1024 points for FFT";   break;
      case TLPAX_MEASMODE_DOUBLE_2048: str = "2 revolutions for one measurement, 2048 points for FFT";   break;
      default:                         str = "unknown";                                                  break;
   }
   return str;
}

ViStatus get_measurement_mode(ViSession ihdl)
{
   ViStatus err;
   ViInt32 mode;
   char const *str;

   err = TLPAX_getMeasurementMode(ihdl, &mode);
   if(err) return err;
   str = get_measurement_mode_label(mode);
   printf("Measurement Mode Reading:\n   (%d) %s\n\n", mode, str);
   return VI_SUCCESS;
}

ViStatus set_measurement_mode(ViSession ihdl)
{
   ViUInt32 mode;

   printf("Set Measurement Mode...\n");
   for(mode = TLPAX_MEASMODE_IDLE; mode <= TLPAX_MEASMODE_DOUBLE_2048; mode++)
   {
      printf("(%d) %s\n", mode, get_measurement_mode_label(mode));
   }

   printf("\nPlease select: ");
   while((mode = getchar()) == EOF);
   mode -= '0';
   fflush(stdin);
   printf("\n");
   if((mode < TLPAX_MEASMODE_IDLE) || (mode > TLPAX_MEASMODE_DOUBLE_2048))
   {
      printf("Invalid selection\n\n");
   }
   else
   {
      return TLPAX_setMeasurementMode(ihdl, mode);
   }
   return VI_SUCCESS;
}

ViStatus get_basic_scan_rate(ViSession ihdl)
{
   ViStatus err;
   ViReal64 bsr;

   err = TLPAX_getBasicScanRate(ihdl, &bsr);
   if(err) return err;
   printf("Basic Sample Rate Reading:\n   %.1f 1/s\n\n", bsr);
   return VI_SUCCESS;
}

ViStatus set_basic_scan_rate(ViSession ihdl)
{
   ViStatus err;
   ViReal64 bsr, min, max;
   char     buf[1000];

   err = TLPAX_getBasicScanRateLimits(ihdl, &min, &max);
   if(err) return err;
   printf("Set Basic Sample Rate in 1/s...\n");
   printf("Enter new Basic Sample rate (%.1f ... %.1f 1/s)\n", min, max);
   scanf("%s", buf);
   sscanf(buf, "%lf\n", &bsr);
   err = TLPAX_setBasicScanRate(ihdl, bsr);
   printf("\n\n");
   fflush(stdin);
   return err;
}

ViStatus get_power_range(ViSession ihdl)
{
   ViStatus err;
   ViReal64 range;
   ViBoolean autorange = VI_FALSE;
   char const *str;

   err = TLPAX_getPowerRange(ihdl, &range);
   if(!err) err = TLPAX_getPowerAutoRange(ihdl, &autorange);
   if(err) return err;
   if(autorange)
   {
      str = "AUTO";
   }
   else
   {
      str = "MANUAL";
   }
   printf("Power Range Reading:\n   %.1f mW (%s)\n\n", range * 1000.0, str);
   return VI_SUCCESS;
}

ViStatus set_power_range(ViSession ihdl)
{
   ViStatus err;
   ViReal64 range, min, max;
   char     buf[1000];

   err = TLPAX_getPowerRangeLimits(ihdl, &min, &max);
   if(err) return err;
   printf("Set Power Range in mW...\n");
   printf("Enter new power range (%.1f ... %.1f mW or 'a' for auto ranging)\n", min * 1000.0, max * 1000.0);
   scanf("%s", buf);
   if(buf[0] == 'a')
   {
      // enable auto ranging
      err = TLPAX_setPowerAutoRange(ihdl, VI_ON);
   }
   else
   {
      sscanf(buf, "%lf\n", &range);
      err = TLPAX_setPowerRange(ihdl, range / 1000.0);
   }
   printf("\n\n");
   fflush(stdin);
   return err;
}

ViStatus get_scan(ViSession ihdl)
{
   ViStatus err;
   ViSession scanId;
   ViReal64 azimuth;
   ViReal64 ellipticity;
   ViReal64 DOP = 0.0;

   err = TLPAX_getLatestScan(ihdl, &scanId);
   if(err) return err;
   printf("Scan Data:\n");
   err = TLPAX_getPolarization(VI_NULL, scanId, &azimuth, &ellipticity);
   if(!err) err = TLPAX_getDOP(VI_NULL, scanId, &DOP, NULL, NULL);
   TLPAX_releaseScan(VI_NULL, scanId);

   if(err) return err;
   printf("Azimuth:     %.1f degree\n", azimuth * 180.0 / PI_VAL);
   printf("Ellipticity: %.1f degree\n", ellipticity * 180.0 / PI_VAL);
   printf("DOP:         %.1f %%\n\n", DOP * 100.0);
   return VI_SUCCESS;
}   

//ViStatus set_scan_multi(ViSession ihdl);
/****************************************************************************
  End of Source file
****************************************************************************/


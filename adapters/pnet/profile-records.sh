#!/bin/sh
# SPDX-License-Identifier: MIT
# profinet-interop: profile records (0xB000-0xBFFF) as application records.
# Run in the p-net tree. Each substitution must match exactly once.
set -eu
sub() { # FILE OLD NEW: replace the text OLD, which must occur once, by NEW
	n=$(OLD="$2" perl -0ne 'my $c = () = /\Q$ENV{OLD}\E/g; print $c' "$1")
	[ "$n" = 1 ] || { echo "profile-records: $1: '$2' matches $n times" >&2; exit 1; }
	OLD="$2" NEW="$3" perl -0pi -e 's/\Q$ENV{OLD}\E/$ENV{NEW}/' "$1"
}
# Stack: a write of a profile index carries no block header (pf_cmrpc.c) and
# goes to the application (pf_cmwrr.c, pf_fspm.c); a read in an AR goes to
# the application and its data is the record (pf_fspm.c, pf_cmrdr.c). A Read
# Implicit has no AR (pf_cmrpc.c) and is not changed: the user record path
# dereferences the AR.
sub src/device/pf_cmrpc.c \
	'      if (p_write_request->index <= PF_IDX_USER_MAX)' \
	'      if ((p_write_request->index <= PF_IDX_USER_MAX) || ((p_write_request->index >= 0xB000) && (p_write_request->index <= 0xBFFF))) /* profinet-interop: profile */'
sub src/device/pf_cmwrr.c \
	'   else if (p_write_request->index <= PF_IDX_USER_MAX)' \
	'   else if ((p_write_request->index <= PF_IDX_USER_MAX) || ((p_write_request->index >= 0xB000) && (p_write_request->index <= 0xBFFF))) /* profinet-interop: profile */'
sub src/device/pf_fspm.c \
	'   if (p_read_request->index <= PF_IDX_USER_MAX)' \
	'   if ((p_read_request->index <= PF_IDX_USER_MAX) || ((p_ar != NULL) && (p_read_request->index >= 0xB000) && (p_read_request->index <= 0xBFFF))) /* profinet-interop: profile */'
sub src/device/pf_fspm.c \
	'   if (p_write_request->index <= PF_IDX_USER_MAX)' \
	'   if ((p_write_request->index <= PF_IDX_USER_MAX) || ((p_write_request->index >= 0xB000) && (p_write_request->index <= 0xBFFF))) /* profinet-interop: profile */'
sub src/device/pf_cmrdr.c \
	'   if (p_read_request->index <= PF_IDX_USER_MAX)' \
	'   if ((p_read_request->index <= PF_IDX_USER_MAX) || ((p_ar != NULL) && (p_read_request->index >= 0xB000) && (p_read_request->index <= 0xBFFF))) /* profinet-interop: profile */'
# Sample: a 16-octet profile record 0xB600 on the Digital Input/Output
# submodule, next to its parameters 123 and 124.
sub samples/pn_dev/app_gsdml.h \
	'#define APP_GSDML_PARAMETER_ECHO_IDX 125' \
	'#define APP_GSDML_PARAMETER_ECHO_IDX 125
#define APP_GSDML_PARAMETER_PROFILE_IDX    0xB600 /* profinet-interop */
#define APP_GSDML_PARAMETER_PROFILE_LENGTH 16'
sub samples/pn_dev/app_gsdml.c \
	'   .parameters = {APP_GSDML_PARAMETER_1_IDX, APP_GSDML_PARAMETER_2_IDX, 0}};' \
	'   .parameters = {APP_GSDML_PARAMETER_1_IDX, APP_GSDML_PARAMETER_2_IDX, APP_GSDML_PARAMETER_PROFILE_IDX, 0}};'
sub samples/pn_dev/app_gsdml.c \
	'      .name = "Echo gain setting",
      .length = APP_GSDML_PARAMETER_LENGTH,
   }};' \
	'      .name = "Echo gain setting",
      .length = APP_GSDML_PARAMETER_LENGTH,
   },
   {
      .index = APP_GSDML_PARAMETER_PROFILE_IDX,
      .name = "Profile record",
      .length = APP_GSDML_PARAMETER_PROFILE_LENGTH,
   }};'
sub samples/pn_dev/app_data.c \
	'static uint32_t app_param_echo_gain = 1; /* Network endianness */' \
	'static uint32_t app_param_echo_gain = 1; /* Network endianness */
static uint8_t app_param_profile[APP_GSDML_PARAMETER_PROFILE_LENGTH]; /* profinet-interop */'
sub samples/pn_dev/app_data.c \
	'      memcpy (&app_param_echo_gain, data, length);
   }' \
	'      memcpy (&app_param_echo_gain, data, length);
   }
   else if (index == APP_GSDML_PARAMETER_PROFILE_IDX)
   {
      memcpy (app_param_profile, data, length);
   }'
sub samples/pn_dev/app_data.c \
	'      *length = sizeof (app_param_echo_gain);
   }' \
	'      *length = sizeof (app_param_echo_gain);
   }
   else if (index == APP_GSDML_PARAMETER_PROFILE_IDX)
   {
      *data = app_param_profile;
      *length = sizeof (app_param_profile);
   }'
test "$(grep -rc 'profinet-interop: profile' src/device | awk -F: '{s+=$2} END {print s}')" = 5

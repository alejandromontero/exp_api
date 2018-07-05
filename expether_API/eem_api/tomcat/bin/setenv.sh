#!/bin/sh

#       Copyright (c) 2015 NEC Corporation
#       NEC CONFIDENTIAL AND PROPRIETARY
#       All rights reserved by NEC Corporation.
#       This program must be used solely for the purpose for
#       which it was furnished by NEC Corporation. No part
#       of this program may be reproduced or disclosed to
#       others, in any form, without the prior written
#       permission of NEC Corporation. Use of copyright
#       notice does not evidence publication of the program.

# Configure JRE to use a non-blocking entropy source to avoid startup delay on
# Linux platform.
JAVA_OPTS="$JAVA_OPTS -Djava.security.egd=file:/dev/./urandom"

export JAVA_OPTS

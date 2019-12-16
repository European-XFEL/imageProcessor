***********************
pplPattern Introduction
***********************

The pplPattern middlelayer device is designed to provide an easy interface
to configure the pattern of the pulse probe laser (ppl).

Due to a specific requirement by LAS group, each instrument must be
able to modify only its relevant bit in the 32-bits pattern associated to
each electron bunch running in the XFEL machine.
This should reduce the possibility to modify by mistake a ppl pattern
configured for a different instrument. 
This feature is obtained at the moment by starting as private user
the karabo server for a specific topic. Upon instantiation of the
pplPattern device the permissions associated to that specific user will be
inherited from the server, thus allowing to expose only the bits relevant
to its topic.

A sequence of up to four patterns can be saved per XFEL train, according
to the needs of the experiment being run in the instruments. In addition,
a *train configuration* can be executed multiple times, and two distinct
train configurations can be set.

The ppl pattern configuration is saved in the DOOCS server
XFEL.UTIL/BUNCH_PATTERN/PATTERN_BUILDER, 
and in order to perform modifications to the pattern the user should
be included in the special group *exfel_lase*. If the user is
not authorized yet the device initialization will fail; in this case
a request should be made to LAS
(e.g., to Tomasz Jezynski <tomasz.jezynski@xfel.eu>).


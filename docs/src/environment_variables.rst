.. _environment_variables:

*********************
Environment Variables
*********************

---------
Telescope
---------

The SKA comprises two telescopes: SKA MID (Dishes) and SKA LOW (Antennas).
The behaviour of code in the ska_oso_scripting module differs depending on
whether it is running in an SKA MID environment (default) or an SKA LOW
environment. For example, when configured for SKA MID, the code will reject
CDM payloads intended for SKA LOW.

The ska-oso-scripting code is configured for MID or LOW by setting the
``SKA_TELESCOPE`` environment variable to either 'skamid' or 'skalow'.
If no environment variable is specified, the code assumes it is controlling
SKA MID.

The telescope setting is also exposed as a configurable value in the
ska-oso-scripting Helm charts, with a default value also set to SKA MID. The
ska-oso-scripting definitions in the skamid and skalow SKAMPI Helm charts set the
appropriate value for their respective deployments.

------------------
Tango Device FQDNs
------------------

The SKA, and so by extension the OET, makes use of Tango Controls to control
the telescope hardware. The Fully Qualified Domain Names (FQDNs) or prefixes
of the Tango devices used to control the central node (telescope) and
sub-arrays are set as environment variables ``CENTRALNODE_FQDN`` and
``SUBARRAYNODE_FQDN_PREFIX`` respectively. These environment variables are set
to the those defined in `values.yaml` when ska-oso-scripting/SKAMPI is deployed.

-----------------------
OSO Data Archive (ODA)
-----------------------

The ODA offers a PostgreSQL or filesystem implementation. The OET can be configured to use
either by setting ``ODA_BACKEND_TYPE`` to ``postgres`` or `filesystem``. There are further environment
variables used by the two implementations which are documented here <TODO> and these can be configured through the
OET Helm chart.


---------------------
Semantic Validation
---------------------

To turn semantic validation off/on in real-time user need to create environment variable into helm charts. 
This will allow user to control semantic validation in real-time.

By using an environment variable, user can easily change the behavior of their application without modifying the code. 
This is particularly useful in different deployment environments (development, testing, production) where 
user might want different validation behaviors.
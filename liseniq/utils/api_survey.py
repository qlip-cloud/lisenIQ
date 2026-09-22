import frappe
import json
import jwt
from time import time
from frappe.utils import now, md_to_html
from frappe.utils.data import get_datetime, add_to_date
from datetime import datetime, timezone
import pytz

AVISO_PRIVACIDAD_TEXT = """Aviso de privacidad
 

Responsable del tratamiento:
Mentum Group

De acuerdo con el artículo 15 de la Constitución Política de Colombia, todas las personas tienen derecho a conocer, actualizar y rectificar la información que se tenga de ellas en las centrales de datos. El presente documento expone como Mentum Group definió procedimientos, políticas que buscan garantizar confianza, seguridad y calidad en el uso de la información de nuestros clientes, talentos y prospectos. La finalidad del tratamiento se efectúa con la recepción, recolección, registro, almacenamiento, conservación, modificación, transferencia, consulta y eliminación de los datos personales, por tanto, el uso de los datos personales es para:

a. Ejecutar la relación contractual existente con sus clientes, proveedores y trabajadores, incluida el pago de obligaciones contractuales.
b. Proveer los servicios y/o los productos requeridos por sus usuarios.
c. Informar sobre nuevos productos o servicios y/o sobre cambios en los mismos.
d. Evaluar la calidad del servicio.
e. Realizar estudios internos sobre hábitos del consumo.
f. Enviar al correo físico, electrónico, celular o dispositivo móvil, vía mensajes de texto (SMS y/o MMS) o a través de cualquier otro medio análogo y/o digital de comunicación creado o por crearse, información comercial, publicitaria o promocional sobre los productos y/o servicios, eventos y/o promociones de tipo comercial o no de estas, con el fin de impulsar, invitar, dirigir, ejecutar, informar y de manera general, llevar a cabo campañas, promociones o concursos de carácter comercial o publicitario, adelantados por Mentum Group, y/o por terceras personas.
g. Desarrollar el proceso de selección, evaluación, vinculación laboral y desvinculación laboral.
h. Soportar procesos de auditoria interna o externa.
i. Registrar la información de los empleados y/o jubilados (activos e inactivos) en las bases de datos de Mentum Group.
j. Los indicados en la autorización otorgada por el titular del dato o descritos en el aviso de privacidad respectivo, según sea el caso.
k. Suministrar, compartir, enviar o entregar sus datos personales a empresas filiales, vinculadas, o subordinadas de Mentum Group, ubicadas en Colombia o cualquier otro país en el evento que dichas compañías requieran la información para los fines aquí indicados.
l. Requerir la autorización de tratamiento de datos personales de las empresas filiales, vinculada o subordinadas de Mentum Group cuando por las dinámicas del negocio se deba dar tratamiento a estos datos personales.

Respecto de los datos (i) recolectados directamente en los puntos de control de seguridad física o lógica, (ii) tomados de los documentos que suministran las personas al personal de seguridad y (iii) obtenidos de las videograbaciones que se realizan dentro o fuera de las instalaciones de Mentum Group, estos se utilizarán para fines de seguridad de las personas, los bienes e instalaciones de Mentum Group, y podrán ser utilizados como prueba en cualquier tipo de proceso de investigación corporativa, disciplinaria y/o judicial (cuando las autoridades Colombianas lo requieran). Si un dato personal es proporcionado, dicha información será utilizada solo para vender, licenciar, transmitir, o divulgar la misma, salvo que: (i) exista autorización expresa para hacerlo: (ii) sea necesario para permitir a los contratistas prestar los servicios encomendados; (iii) sea necesario con el fin de proveer nuestros servicios y/o productos; (iv) sea necesario divulgarla a las entidades que prestan servicios de mercadeo en nombre de Mentum Group, o a otras entidades con las cuales se tengan acuerdos de mercado conjunto, (v) la información tenga relación con una fusión, consolidación, adquisición, desinversión, u otro proceso de restructuración de la sociedad; (vi) que sea requerido o permitido por la ley.

Mentum Group, podrá subcontratar a tercero para el procesamiento de determinadas funciones o información. Cuando efectivamente se subcontrate con terceros el procesamiento de información personal o se proporcione información personal a terceros prestadores de servicios, Mentum Group, advierte a dichos terceros sobre la necesidad de proteger dicha información personal con medidas de seguridad apropiadas, se prohíbe el uso de la información para fines propios y se solicita que no se divulgue la información personal a otros.
Derechos de los titulares de datos personales: los titulares de datos personales por sí o por intermedio de su representante y/o apoderado a si causahabiente podrán ejercer los siguientes derechos, respecto de los datos personales que sean objeto de tratamiento por parte de Mentum Group, tales como:

1. Derecho de acceso: en virtud del cual podrá acceder a los datos personales que estén bajo el control de Mentum Group, para efectos de consultarlos de manera gratuita al menos una vez cada mes calendario, y cada vez que existan modificaciones sustanciales de las políticas de tratamiento de la información que motiven nuevas consultas.
2. Derecho de actualización, rectificación y supresión: en virtud del cual podrá solicitar la actualización, rectificación y/o supresión de los datos personales objeto de tratamiento, de tal manera que se satisfagan los propósitos del tratamiento.}
3. Derecho a solicitar prueba de la autorización: salvo en los eventos en los cuales, según las normas legales vigentes, no se requiera de la autorización para realizar el tratamiento.
4. Derecho a ser informado: respecto del uso del dato personal.
5. Derecho a presentar quejas ante la superintendencia de industria y comercio: por infracciones a los dispuesto en la normatividad vigente sobre tratamiento de datos personales.
6. Derecho a requerir el cumplimiento: de las órdenes emitidas por la Superintendencia de Industria y Comercio.

Para ejercer los derechos de conocer, actualizar, rectificar y/o suprimir los datos personales para este último siempre y cuando no exista una relación contractual, puede usar los siguientes medios:

• Correo electrónico: datospersonales@mentum.group
• Solicitar la política de tratamiento de datos personales al correo electrónico aquí dispuesto.
• Todo cambio que se presente será notificado a través del correo electrónico aquí dispuesto.
• En el evento que se recolecten datos personales sensibles, el titular podrá negarse a autorizar su tratamiento siempre y cuando no exista una relación contractual o se prevea tenerla.
• Mentum Group, será la responsable de atender las peticiones, quejas y reclamos que formule el titular del dato en ejercicio de los derechos contemplados en el apartado: “Deberes cuando realiza el tratamiento a través de encargado” de la política de tratamiento de datos personales, a excepción del descrito en su literal e). Para tales efectos, el titular del dato personal o quien ejerza su representación podrá enviar su petición, queja o reclamo de lunes a viernes de 8:00 AM a 4:30 PM al correo electrónico datospersonales@mentum.group, llamar al teléfono fijo de Bogotá +571-601-508-8877 , o radicarla en la siguiente dirección: Cl. 98 Bis #71D-20."""

POLITICAS_TRATAMIENTO_TEXT = """POLÍTICA PARA EL TRATAMIENTO DE DATOS PERSONALES
 

ALCANCE
Dando cumplimiento a lo dispuesto en la Ley estatutaria 1581 de 2012 y a su Decreto Reglamentario 1377 de 2013, MENTUM GROUP, adopta la presente política para el tratamiento de datos personales respecto de la recolección, almacenamiento, uso, circulación, supresión y de todas aquellas actividades que constituyan tratamiento de datos personales, la cual será informada a todos los titulares de los datos recolectados o que en un futuro se obtengan como producto del ejercicio del objeto social relacionado con las actividades comerciales o laborales.

MENTUM GROUP conformado por la alianza entre BIT CONSULTING S.A. con NIT: 830005677, 2 IN SOLUTIONS con NIT: 830139842, COMERCIALIZADORA DE SOFTWARE Y SOLUCIONES SAS, con NIT: 900566693, NOOVA, con NIT: 901108864 domiciliadas en la ciudad de Bogotá, en la Cl. 98 Bis #71D-20, manifiesta que garantiza los derechos de la privacidad, la intimidad, el buen nombre y la autonomía, en el tratamiento de los datos personales, y en consecuencia todas sus actuaciones se regirán por los principios de legalidad, finalidad, libertad, veracidad, calidad, transparencia, acceso como circulación restringida, seguridad y confidencialidad.

Todas las personas que en desarrollo de diferentes actividades comerciales y/o contractuales, laborales, entre otras, sean permanentes u ocasionales, que llegasen a suministrar cualquier tipo de información o dato personal a MENTUM GROUP podrá conocerla, actualizarla, rectificarla, suprimirla o revocar la autorización previamente otorgada.

Así mismo se faculta a MENTUM GROUP consultar a partir de los datos personales suministrados las listas de personas y entidades con organizaciones terrorista, vinculante para Colombia. Con el fin de dar cumplimiento a lo dispuesto por la ley 1474 de 2011 y a la convención Interamericana Contra la Corrupción.

DEFINICIONES
Para efectos de la ejecución de la presente política y de conformidad con la normatividad legal colombiana, serán aplicables las siguientes definiciones:

Autorización: Consentimiento previo, expreso e informado de la persona titular para llevar a cabo el Tratamiento de datos personales.

Aviso de privacidad: Documento físico, electrónico o en cualquier otro formato generado por el responsable que se pone a disposición de la persona titular para el tratamiento de sus datos personales. En el aviso de privacidad se comunica a la persona titular la información relativa a la existencia de las políticas de tratamiento de información que le serán aplicables, la forma de acceder a las mismas y la finalidad del tratamiento que se pretende dar a los datos personales.

Base de Datos: Conjunto organizado de datos personales que son objeto de tratamiento de acuerdo con lo dispuesto por la organización en cumplimiento con la ley.

Dato personal: Cualquier tipo de información que esté vinculada o pueda vincularse a una persona natural y organización determina o determinable.

Dato público: Es el dato calificado como tal según los mandatos de la ley o de la Constitución Política y aquel que no sea semiprivado, privado o sensible. Son públicos, entre otros, los datos relativos al estado civil de las personas, a su profesión u oficio, a su calidad de comerciante o de servidor público y aquellos que puedan obtenerse sin reserva alguna. Por su naturaleza, los datos públicos pueden estar contenidos, entre otros, en registros públicos, documentos públicos.

Dato privado: Es el dato que por su naturaleza íntima o reservada sólo es relevante para la persona titular.

Datos sensibles: Se entiende por datos sensibles aquellos que afectan la intimidad de la persona titular o cuyo uso indebido puede generar su discriminación, tales como aquellos que revelen el origen racial o étnico, la orientación política, las convicciones religiosas o filosóficas, la pertenencia a sindicatos, organizaciones sociales, de derechos humanos o que promueva intereses de cualquier partido político o que garanticen los derechos y garantías de partidos políticos de oposición, así como los datos relativos a la salud, a la vida sexual y los datos biométricos.

Encargado del Tratamiento: Persona natural o jurídica, pública o privada, que por sí misma o en asocio con otros, realice el tratamiento de datos personales por cuenta del responsable del tratamiento.

Responsable del Tratamiento: Persona natural o jurídica, pública o privada, que por sí misma o en asocio con otros, decida sobre la base de datos y/o el tratamiento de los datos.

Titular: Persona natural cuyos datos personales sean objeto de tratamiento.

Tratamiento: Cualquier operación o conjunto de operaciones sobre datos personales, tales como la recolección, almacenamiento, uso, circulación o supresión de estos.

FINALIDAD Y TRATAMIENTO DE LOS DATOS PERSONALES
La recolección y tratamiento de datos personales por parte de MENTUN GROUP tiene como finalidad el uso para:

Ejecutar la relación contractual existente con sus clientes, proveedores y trabajadores, incluida el pago de obligaciones contractuales.
Proveer los servicios y/o los productos requeridos por sus usuarios.
Informar sobre nuevos productos o servicios y/o sobre cambios en los mismos.
Evaluar la calidad del servicio.
Realizar estudios internos sobre hábitos de consumo.
Enviar al correo físico, electrónico, celular o dispositivo móvil, vía mensajes de texto (SMS y/o MMS) o a través de cualquier otro medio análogo y/o digital de comunicación creado o por crearse, información comercial, publicitaria o promocional sobre los productos y/o servicios, eventos y/o promociones de tipo comercial o no de estas, con el fin de impulsar, invitar, dirigir, ejecutar, informar y de manera general, llevar a cabo campañas, promociones o concursos de carácter comercial o publicitario, adelantados por MENTUM GROUP, y/o por terceras personas.
Desarrollar el proceso de selección, evaluación, y vinculación laboral.
Soportar procesos de auditoría interna o externa.
Registrar la información de empleados y/o pensionados (activos e inactivos) en las bases de datos de MENTUM GROUP.
Los indicados en la autorización otorgada por el titular del dato o descritos en el aviso de privacidad respectivo, según sea el caso.
Suministrar, compartir, enviar o entregar sus datos personales a empresas filiales, vinculadas, o subordinadas de MENTUM GROUP ubicadas en Colombia o cualquier otro país en el evento que dichas compañías requieran la información para los fines aquí indicados.
MENTUM GROUP podrá realizar consultas en bases de datos restrictivas, tales como listas de sanciones, listas de personas expuestas políticamente (PEP), y otras bases de datos similares, con el fin de dar cumplimiento a su política de SARLAFT. Estas consultas se llevarán a cabo de acuerdo con la normativa vigente y con el objetivo de prevenir y detectar actividades ilícitas, garantizando la protección de los datos personales de nuestros clientes y usuarios. Los titulares serán informados sobre esta práctica en el aviso de privacidad.
 

DEBERES DE MENTUM GROUP
Todos los obligados a cumplir esta política deben tener presente que MENTUM GROUP, está obligada a cumplir los deberes que al respecto imponga la ley. En consecuencia, se deben cumplir las siguientes obligaciones:

DEBERES CUANDO ACTÚA COMO RESPONSABLE
Solicitar y conservar, en las condiciones previstas en esta política, copia de la respectiva autorización otorgada por el titular.
Informar de manera clara y suficiente al titular sobre la finalidad de la recolección y los derechos que le asisten por virtud de la autorización otorgada.
Informar a solicitud de la persona titular sobre el uso dado a sus datos personales.
Tramitar las consultas y reclamos formulados en los términos señalados en la presente política.
Procurar que los principios de veracidad, calidad, seguridad y confidencialidad en los términos establecidos en la siguiente política.
Conservar la información bajo las condiciones de seguridad necesarias para impedir su adulteración, pérdida, consulta, uso o acceso no autorizado o fraudulento.
Actualizar la información cuando sea necesario.
Rectificar los datos personales cuando ello sea procedente.
Notificar alguna irregularidad a los organismos de control como la fiscalía general de la nación y/o policía internacional cuando se encuentre un reporte en las listas de personas asociadas con organizaciones terroristas, vinculantes para Colombia.
Aplicar el reglamento interno de trabajo y protocolos de MENTUM GROUP para garantizar el debido proceso de tener que aplicarse el numeral (9) de los DEBERES CUANDO ACTÚA COMO RESPONSABLE
DEBERES CUANDO OBRA COMO ENCARGADO DEL TRATAMIENTO DE DATOS PERSONALES
Si realiza el tratamiento de datos en nombre de otra entidad u organización (responsable del tratamiento) deberá cumplir los siguientes deberes:

Establecer que el responsable del tratamiento esté autorizado para suministrar los datos personales que tratará como Encargado.
Garantizar al titular, en todo tiempo, el pleno y efectivo ejercicio del derecho de hábeas data.
Conservar la información bajo las condiciones de seguridad necesarias para impedir su adulteración, pérdida, consulta, uso o acceso no autorizado o fraudulento.
Realizar oportunamente la actualización, rectificación o supresión de los datos.
Actualizar la información reportada por los responsables del tratamiento dentro de los cinco (5) días hábiles contados a partir de su recibo.
Tramitar las consultas y los reclamos formulados por los titulares en los términos señalados en la presente política.
Registrar en la base de datos la leyenda “reclamo en trámite” en la forma en que se establece en la presente política.
Insertar en la base de datos la leyenda “información en discusión judicial” una vez notificado por parte de la autoridad competente sobre procesos judiciales relacionados con la calidad del dato personal.
Abstenerse de circular información que esté siendo controvertida por el titular y cuyo bloqueo haya sido ordenado por la Superintendencia de Industria y Comercio.
Permitir el acceso a la información únicamente a las personas autorizadas por el titular o facultadas por la ley para dicho efecto.
Informar a la Superintendencia de Industria y Comercio cuando se presenten violaciones a los códigos de seguridad y existan riesgos en la administración de la información de los titulares.
Cumplir las instrucciones y requerimientos que imparta la Superintendencia de Industria y Comercio.
Solicitar la autorización de tratamiento de datos personales a las empresas filiales, vinculadas o subordinadas de Mentum Group cuando por la dinámica del negocio se requiera dar tratamiento a los datos personales de estas.
Consultar de manera anual las listas de personas y entidades asociadas con organizaciones terroristas, vinculantes para Colombia y notificar la responsable del tratamiento de los datos personales las irregularidades que se puedan encontrar.
DEBERES CUANDO REALIZA EL TRATAMIENTO A TRAVÉS DEL ENCARGADO
Suministrar al Encargado del tratamiento únicamente los datos personales cuyo tratamiento esté previamente autorizado. Para efectos de la transmisión nacional o internacional de los datos se deberá suscribir un contrato de transmisión de datos personales o pactar cláusulas contractuales según lo establecido en el artículo 25 del Decreto 1377 de 2013.
Garantizar que la información que se suministre al encargado del tratamiento sea veraz, completa, exacta, actualizada, comprobable y comprensible.
Comunicar de forma oportuna al Encargado del tratamiento todas las novedades respecto de los datos que previamente le haya suministrado y adoptar las demás medidas necesarias para que la información suministrada a este se mantenga actualizada.
Informar de manera oportuna al encargado del tratamiento las rectificaciones realizadas sobre los datos personales para que éste proceda a realizar los ajustes pertinentes.
Exigir al Encargado del tratamiento, en todo momento, el respeto a las condiciones de seguridad y privacidad de la información del titular.
Informar al encargado del tratamiento cuando determinada información se encuentre en discusión por parte del titular, una vez se haya presentado la reclamación y no haya finalizado el trámite respectivo.
Solicitar al encargado de manera regular (una vez al año) la actualización de los datos personales de los talentos, proveedores, contratistas, clientes y general con cualquier persona y entidad que tenga una relación comercial con MENTUM GROUP.
DEBERES RESPECTO DE LA SUPERINTENDENCIA DE INDUSTRIA Y COMERCIO
Informarle las eventuales violaciones a los códigos de seguridad y la existencia de riesgos en la administración de la información de los titulares.
Cumplir las instrucciones y requerimientos que imparta la Superintendencia de Industria y Comercio.
SOLICITUD DE AUTORIZACIÓN AL TITULAR DEL DATO PERSONAL
Con antelación y/o al momento de efectuar la recolección del dato personal, MENTUM GROUP solicitará al titular del dato su autorización para efectuar su recolección y tratamiento, indicando la finalidad para la cual se solicita el dato. La autorización se podrá solicitar a través de medios técnicos automatizados (como formularios en línea), escritos (como formularios físicos) u orales (como grabaciones de llamadas telefónicas). La prueba de la autorización se conservará mediante registros electrónicos, copias físicas de formularios firmados o grabaciones de audio, según corresponda.

Los medios de recolección directamente en los puntos de seguridad, tomados de los documentos que suministran las personas al personal de seguridad y obtenidos de las videograbaciones que se realizan dentro o fuera de las instalaciones de MENTUM GROUP, éstos se utilizarán para fines de seguridad de las personas, los bienes e instalaciones de MENTUM GROUP y podrán ser utilizados como prueba en cualquier tipo de proceso. Si un dato personal es proporcionado, dicha información será utilizada sólo para los propósitos aquí señalados, y por tanto, MENTUM GROUP no procederá a vender, licenciar, transmitir, o divulgar la misma, salvo que exista autorización expresa para hacerlo; sea necesario para permitir a los contratistas prestar los servicios encomendados; sea necesario con el fin de proveer nuestros servicios y/o productos;  sea necesario divulgarla a las entidades que prestan servicios de mercadeo en nombre de MENTUM GROUP o a otras entidades con las cuales se tengan acuerdos de mercado conjunto; la información tenga relación con una fusión, consolidación, adquisición, desinversión, u otro proceso de restructuración de la sociedad; que sea requerido o permitido por la ley.

MENTUM GROUP, podrá subcontratar a terceros para el procesamiento de determinadas funciones o información. Cuando efectivamente se subcontrate con terceros el procesamiento de información personal o se proporcione información personal a terceros prestadores de servicios, MENTUM GROUP, advierte a dichos terceros sobre la necesidad de proteger dicha información personal con medidas de seguridad apropiadas, se prohíbe el uso de la información para fines propios y se solicita que no se divulgue la información personal a otros.

SEGURIDAD DE LA INFORMACIÓN
MENTUM GROUP está comprometido con la seguridad y tratamiento adecuado de los datos personales contenidos en los activos de la información, evitando el acceso no autorizado a terceros que puedan conocer, modificar, divulgar y/o destruir información que allí reposa. Para este fin cuenta con un conjunto de controles de seguridad que permiten proteger la infraestructura tecnológica en la que se almacena, procesa y trasmite la información.  El acceso a las diferentes bases de datos se encuentra restringido incluso para los funcionarios y contratistas, otorgando acceso a quienes estrictamente lo requieren para realizar sus funciones y actividades. Así mismo todos los funcionarios, contratistas, proveedores se encuentran comprometidos con la confidencialidad de la información, atendiendo a los lineamientos sobre tratamiento de la información establecida en la ley.

MEDIDAS DE SEGURIDAD 
En desarrollo del principio de seguridad establecido en la Ley 1581 de 2012 MENTUM GROUP, adoptará las medidas técnicas, humanas y administrativas que sean necesarias para otorgar seguridad a los registros evitando su adulteración, pérdida, consulta, uso o acceso no autorizado o fraudulento. El personal que realice el tratamiento de los datos personales ejecutará los protocolos establecidos con el fin de garantizar la seguridad de la información.

LIMITACIONES TEMPORALES AL TRATAMIENTO DE LOS DATOS PERSONALES 
MENTUM GROUP, solo podrá recolectar, almacenar, usar o circular los datos personales durante el tiempo que sea razonable y necesario, de acuerdo con las finalidades que justificaron el tratamiento, atendiendo a las disposiciones aplicables a la materia de que se trate y a los aspectos administrativos, contables, fiscales, jurídicos e históricos de la información. Una vez cumplida la o las finalidades del tratamiento y sin perjuicio de normas legales que dispongan lo contrario, procederá a la supresión de los datos personales en su posesión. No obstante, lo anterior, los datos personales deberán ser conservados cuando así se requiera para el cumplimiento de una obligación legal o contractual.

PROCEDIMIENTO PARA CONSULTA Y RECLAMACIONES
La petición, queja o reclamo deberá contener la identificación de la persona titular, la descripción de los hechos que dan lugar al reclamo, la dirección, y acompañando los documentos que se quiera hacer valer.

CONSULTAS: El titular o sus causahabientes, podrán consultar la información personal que repose en las bases de datos de MENTUM GROUP, previa solicitud del mismo, la cual será atendida en un plazo máximo de diez (10) días hábiles contados a partir de la fecha de recibo. En el evento de no ser posible atender la solicitud en dicho término, se informará al interesado dentro del mismo término, expresando los motivos que dan lugar a la imposibilidad, al igual que la fecha en que se dará respuesta, la cual no podrá ser superior a cinco (5) días hábiles siguientes al vencimiento del primer plazo. 

RECLAMOS: El Titular o sus causahabientes que consideren que la información contenida en una base de datos debe ser objeto de corrección, actualización o supresión, o cuando adviertan el presunto incumplimiento de cualquiera de los deberes contenidos en esta ley, podrán presentar un reclamo ante MENTUM GROUP el cual será tramitado bajo las siguientes reglas:

El reclamo se formulará mediante solicitud dirigida a MENTUM GROUP, con la identificación del Titular, la descripción de los hechos que dan lugar al reclamo, la dirección, y acompañando los documentos que se quiera hacer valer. Si el reclamo resulta incompleto, se requerirá al interesado dentro de los cinco (5) días siguientes a la recepción del reclamo para que subsane las fallas. Transcurridos dos (2) meses desde la fecha del requerimiento, sin que el solicitante presente la información requerida, se entenderá que ha desistido del reclamo. En caso de que quien reciba el reclamo no sea competente para resolverlo, dará traslado a quien corresponda en un término máximo de dos (2) días hábiles e informará de la situación al interesado.
Una vez recibido el reclamo completo, se incluirá en la base de datos (mesa de ayuda de soporte) una leyenda que diga «reclamo en trámite» y el motivo del mismo, en un término no mayor a dos (2) días hábiles. Dicha leyenda deberá mantenerse hasta que el reclamo sea decidido.
El término máximo para atender el reclamo será de quince (15) días hábiles contados a partir del día siguiente a la fecha de su recibo. Cuando no fuere posible atender el reclamo dentro de dicho término, se informará al interesado los motivos de la demora y la fecha en que se atenderá su reclamo, la cual en ningún caso podrá superar los ocho (8) días hábiles siguientes al vencimiento del primer término.
El titular o su representante podrá solicitar a MENTUM GROUP, la rectificación, actualización o supresión de sus datos personales, previa acreditación de su identidad. Cuando la solicitud sea formulada por persona distinta del titular y no se acredita que la misma actúa en representación de aquél, se tendrá por no presentada. La solicitud de rectificación, actualización o supresión tendrá que ser presentada a través de los medios habilitados por MENTUM GROUP., y contener como mínimo lo siguiente:
Nombre y domicilio del titular o cualquier otro medio para recibir respuesta.
Documentos que acreditan la identidad o la personalidad de su representante.
Descripción clara y precisa de los datos personales que dan lugar al reclamo.
PARÁGRAFO 1. RECTIFICACIÓN Y ACTUALIZACIÓN: Cuando los reclamos tengan por objeto la rectificación o actualización, el titular deberá indicar las correcciones a realizar y adoptar la documentación que avale su petición.

PARÁGRAFO 2. SUPRESIÓN: La supresión de datos personales se realiza mediante la eliminación total o parcial de la información personal según lo solicitado por el titular, no obstante, lo cual MENTUM GROUP podrá negarse a la misma cuando el titular tenga un deber legal o contractual de permanecer en la base de datos. Revocatoria de la autorización. Los titulares de los datos personales pueden revocar la autorización concedida en cualquier momento, exceptuando de lo anterior aquellos eventos en los cuales lo impida una disposición legal o contractual. En todo caso, el titular deberá indicar en su solicitud si se trata de un revocatorio total o parcial, esto último cuando sólo quiera eliminarse alguna de las finalidades para la cual se autorizó el tratamiento, escenario en el que el titular deberá indicar la finalidad que desea eliminar. 

PROCESO RESPONSABLE DEL DATO PERSONAL
MENTUM GROUP, será responsable de atender las peticiones, quejas y reclamos que formule el titular del dato en ejercicio de los derechos contemplados en esta política o quien ejerza su representación podrá enviar su petición, queja o reclamo de lunes a viernes de 8:00 AM a 4:30 PM al correo electrónico datospersonales@mentum.group, llamar al teléfono fijo de Bogotá teléfono +57 +601 508 8877 ext. 57058 o radicarla en la siguiente dirección: Cl. 98 Bis #71D-20.
 

CAPACITACIÓN Y CONCIENTIZACIÓN
Capacitación y Concientización MENTUM GROUP proporcionará capacitación periódica a todos los talentos sobre la prevención del lavado de activos y la financiación del terrorismo, incluyendo la identificación de señales de alerta y el cumplimiento de la normativa vigente. Además, se realizarán sesiones de concientización sobre la importancia de la protección de datos personales y las mejores prácticas para su tratamiento seguro.

FECHA DE ENTRADA EN VIGENCIA 
La presente Política de Datos Personales será revisada y actualizada periódicamente, al menos una vez al año, o cuando se presenten cambios significativos en la normativa aplicable o en los procesos internos de MENTUM GROUP. Cualquier cambio que se presente respecto de la presente política, se informará a través de la dirección electrónica: datospersonales@MENTUM.GROUP y otros medios de comunicación pertinentes."""

def get_legal_modals_html():
    """
    Genera el HTML, CSS y JS necesarios para renderizar los modales en la misma vista de bienvenida.
    Los textos se incrustan en el HTML para evitar redirecciones.
    """
    html = """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Rubik:wght@400&display=swap');

      .iq-modal-overlay {
          display: none;
          position: fixed;
          z-index: 10000;
          left: 0;
          top: 0;
          width: 100%;
          height: 100%;
          background-color: rgba(0,0,0,0.6);
          backdrop-filter: blur(4px);
          overflow-y: auto;
      }
      .iq-modal-box {
          background-color: #fff;
          margin: 5% auto;
          padding: 30px;
          border-radius: 12px;
          width: 90%;
          max-width: 800px;
          box-shadow: 0 10px 25px rgba(0,0,0,0.2);
          position: relative;
          font-family: 'Rubik', sans-serif;
      }
      .iq-modal-close {
          position: absolute;
          right: 20px;
          top: 20px;
          font-size: 24px;
          font-weight: bold;
          color: #888;
          cursor: pointer;
          transition: color 0.2s;
          line-height: 1;
      }
      .iq-modal-close:hover {
          color: #111;
      }
      .iq-modal-title {
          margin-top: 0;
          margin-bottom: 20px;
          font-size: 1.5rem;
          color: #7B24FF;
          border-bottom: 1px solid #eee;
          padding-bottom: 15px;
      }
      .iq-modal-body {
          font-size: 14px;
          font-weight: 400;
          color: #6c757d;
          line-height: 1.6;
          white-space: pre-wrap;
          word-break: break-word;
          overflow-wrap: break-word;
          max-height: 60vh;
          overflow-y: auto;
          overflow-x: hidden;
          padding-right: 10px;
          text-align: justify;
      }
      .iq-modal-body::-webkit-scrollbar {
          width: 8px;
      }
      .iq-modal-body::-webkit-scrollbar-thumb {
          background: #ccc;
          border-radius: 4px;
      }
    </style>

    <div id="iqPrivacyModal" class="iq-modal-overlay" onclick="closeIqModalOnClickOutside(event, 'iqPrivacyModal')">
      <div class="iq-modal-box">
        <span class="iq-modal-close" onclick="closeIqModal('iqPrivacyModal')">&times;</span>
        <h2 class="iq-modal-title">Aviso de Privacidad</h2>
        <div class="iq-modal-body">__AVISO_PRIVACIDAD_TEXT__</div>
      </div>
    </div>

    <div id="iqPolicyModal" class="iq-modal-overlay" onclick="closeIqModalOnClickOutside(event, 'iqPolicyModal')">
      <div class="iq-modal-box">
        <span class="iq-modal-close" onclick="closeIqModal('iqPolicyModal')">&times;</span>
        <h2 class="iq-modal-title">Políticas de Tratamiento</h2>
        <div class="iq-modal-body">__POLITICAS_TRATAMIENTO_TEXT__</div>
      </div>
    </div>

    <script>
      function openIqModal(e, modalId) {
        if(e) e.preventDefault();
        var modal = document.getElementById(modalId);
        if(modal) modal.style.display = 'block';
      }
      function closeIqModal(modalId) {
        var modal = document.getElementById(modalId);
        if(modal) modal.style.display = 'none';
      }
      function closeIqModalOnClickOutside(event, modalId) {
        if (event.target.id === modalId) {
          closeIqModal(modalId);
        }
      }
    </script>
    """
    
    html = html.replace("__AVISO_PRIVACIDAD_TEXT__", AVISO_PRIVACIDAD_TEXT)
    html = html.replace("__POLITICAS_TRATAMIENTO_TEXT__", POLITICAS_TRATAMIENTO_TEXT)
    
    return html

def generate_default_welcome_markdown(payload: dict) -> str:
    """
    Genera el mensaje de bienvenida por defecto en formato Markdown estructurado.
    Reemplaza las variables dinámicas de forma segura y ahora utiliza enlaces HTML con eventos onClick para abrir modales.
    """
    nombre_medicion = payload.get("nombre_medicion", "")
    numero_preguntas = payload.get("numero_preguntas", 0)
    
    # Validación segura del número de preguntas
    if not isinstance(numero_preguntas, int):
        try:
            numero_preguntas = int(numero_preguntas)
        except (ValueError, TypeError):
            numero_preguntas = 0

    # Usamos etiquetas HTML locales <a> apuntando a la función JS openIqModal
    markdown_template = f"""Gracias por dedicar unos minutos para responder esta medición. 
    
Tu opinión es muy importante y nos ayudará a comprender mejor la experiencia de las personas, identificar oportunidades de mejora y tomar decisiones basadas en información confiable.

Antes de comenzar, ten en cuenta lo siguiente:

- Consta de {numero_preguntas} preguntas.
- No existen respuestas correctas o incorrectas; responde con total sinceridad.
- La información será utilizada únicamente para los fines definidos por la organización.
- Antes de continuar, debes leer y aceptar los Términos y Condiciones y el Aviso de Privacidad relacionados con esta medición.

[ ] He leído y acepto el <a href="#" onclick="openIqModal(event, 'iqPrivacyModal')" style="text-decoration: underline; color: #007bff; font-weight: bold;">Aviso de Privacidad</a> y la <a href="#" onclick="openIqModal(event, 'iqPolicyModal')" style="text-decoration: underline; color: #007bff; font-weight: bold;">Política de Tratamiento de Datos</a> para participar en esta medición.

Cuando estés listo, haz clic en "Comenzar" para iniciar la medición."""

    return markdown_template

def _now_utc_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def _now_in_survey_tz_by_su_name(su_name: str) -> datetime:
    try:
        tz_name = (frappe.db.get_value("qp_IQ_Survey", {"su_name": su_name}, "su_timezone") or "UTC").strip()
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.utc
    return datetime.now(tz)

@frappe.whitelist(allow_guest=True)
def get_public_survey(survey_name, token=None, dni=None):
  if dni and str(dni).strip().lower() in ["null", "none", "undefined", ""]:
      dni = None
      
  try:
    survey_data = frappe.db.get_value("Survey", survey_name, ["survey_json", "theme_json"], as_dict=True)
    if not survey_data:
        frappe.throw("Encuesta no encontrada.")
        
    # Verificar si es una medición de Liderazgo (360) para aplicar cambios dinámicos de preguntas
    survey_doc = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, ["name", "su_is_leadership", "su_owner"], as_dict=True)
    
    if survey_doc:
        survey_data["is_leadership"] = survey_doc.su_is_leadership
    
    if survey_doc and survey_doc.su_is_leadership:
        recipient = None
        
        # Intentar obtener el destinatario por medio del token
        if token and token != "Anonimo":
            secret = _get_jwt_secret()
            try:
                payload = jwt.decode(token, secret, algorithms=["HS256"])
                rid = payload.get("rid")
                if rid:
                    recipient = frappe.db.get_value("qp_IQ_SurveyRecipient", rid, ["sr_evaluation_role", "sr_evaluating_to", "sr_contact"], as_dict=True)
                else:
                    recipient = frappe.db.get_value("qp_IQ_SurveyRecipient", {"sr_token": token}, ["sr_evaluation_role", "sr_evaluating_to", "sr_contact"], as_dict=True)
            except Exception:
                pass
        
        # Si no hay token personalizado, buscar por DNI
        if not recipient and dni:
            contact_name = frappe.db.get_value("Contact", {"custom_document_number": dni, "custom_company": survey_doc.su_owner}, "name")
            if contact_name:
                recipients = frappe.get_all(
                    "qp_IQ_SurveyRecipient", 
                    filters={"sr_survey": survey_doc.name, "sr_contact": contact_name, "sr_status": ["!=", "Responded"]}, 
                    fields=["sr_evaluation_role", "sr_evaluating_to", "sr_contact"],
                    limit_page_length=1
                )
                if recipients:
                    recipient = recipients[0]
        
        if recipient:
            # Validar si cumple condición de Autoevaluación
            is_auto = (recipient.sr_evaluation_role == "Autoevaluación" and recipient.sr_evaluating_to == recipient.sr_contact)
            
            # Si evalúa a un tercero, reemplazar enunciado por qn_statement_others
            if not is_auto:
                parsed_json = json.loads(survey_data.survey_json)
                survey_questions = frappe.get_all("qp_IQ_SurveyQuestion", filters={"parent": survey_doc.name}, fields=["sq_question"])
                
                q_dict = {}
                for sq in survey_questions:
                    other_stmt = frappe.db.get_value("qp_IQ_Question", sq.sq_question, "qn_statement_others")
                    if other_stmt:
                        q_dict[sq.sq_question] = other_stmt
                        
                for page in parsed_json.get("pages", []):
                    for el in page.get("elements", []):
                        q_name = el.get("name")
                        if q_name in q_dict:
                            el["title"] = q_dict[q_name]
                
                survey_data["survey_json"] = json.dumps(parsed_json)
                
    return survey_data
  except Exception as e:
    frappe.log_error(frappe.get_traceback(), 'Error en get_public_survey')
    frappe.throw("No se pudo cargar la encuesta solicitada.")

@frappe.whitelist(allow_guest=True)
def save_survey_response(survey_name, response_data, user=None):
  try:
    data = json.loads(response_data)

    token_like = False
    if user and user != "Anonimo":
      if "." in user or len(user) > 140:
        token_like = True

    if token_like:
      data["__token"] = user
      user_to_store = "Anonimo"
    else:
      user_to_store = user or "Anonimo"
    
    new_response = frappe.get_doc({
        "doctype": "Survey Response",
        "survey": survey_name,
        "response_json": json.dumps(data),
        "user": user_to_store
    })
    
    new_response.insert(ignore_permissions=True)
    
    return {"status": "Ok", "message": "Respuesta guardada con éxito."}

  except Exception as e:
    frappe.log_error(frappe.get_traceback(), 'Error en save_survey_response')
    frappe.throw("Ocurrió un error al guardar tu respuesta.")

def _get_jwt_secret():
  return frappe.conf.get("liseniq_jwt_secret") or frappe.conf.get("encryption_key")

@frappe.whitelist(allow_guest=True)
def get_survey_is_anonymous(survey_name):
    is_anonymous = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "su_is_anonymous")
    return bool(is_anonymous)

@frappe.whitelist(allow_guest=True)
def validate_survey_link(survey_name, user=None, token=None, dni=None, uq=None):
  if dni and str(dni).strip().lower() in ["null", "none", "undefined", ""]:
      dni = None
      
  uq_flag = str(uq).lower() == "true"
  try:
    status_finished = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")
    status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
    rs_responded = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Responded"}, "name") or "Responded"
    
    # Extraemos los campos su_term_subject y su_term_body para personalizar la pantalla de bienvenida
    survey_doc = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, 
        ["name", "su_status", "su_start_date", "su_end_date", "su_is_leadership", "su_owner", "su_term_subject", "su_term_body", "su_default_welcome"], 
        as_dict=True)
        
    if not survey_doc:
         return {"allow": False, "message": "Encuesta no encontrada."}
         
    su_status = survey_doc.su_status
    su_start_date = survey_doc.su_start_date
    su_end_date = survey_doc.su_end_date
    survey_name_id = survey_doc.get("name")
    is_leadership = survey_doc.su_is_leadership
    
    # Determinar los valores de bienvenida
    welcome_subject = survey_doc.get("su_term_subject")
    welcome_message = survey_doc.get("su_term_body") or ""

    if survey_doc.get("su_default_welcome"):
        numero_preguntas = frappe.db.count("qp_IQ_SurveyQuestion", {"parent": survey_name_id}) if survey_name_id else 0
        payload = {
            "nombre_medicion": survey_name,
            "numero_preguntas": numero_preguntas
        }
        # Inyectar Asunto y Cuerpo transformando Markdown a HTML Nativo
        welcome_subject = f"¡Bienvenido/a a la medición {survey_name}!"
        raw_markdown = generate_default_welcome_markdown(payload)
        welcome_message = md_to_html(raw_markdown)

    # Añadir siempre la lógica y HTML de los modales para que estén disponibles
    # incluso si usan una plantilla personalizada que invoque los onClick
    if welcome_message:
        welcome_message += get_legal_modals_html()

    # Respuesta exitosa base incluyendo campos de bienvenida personalizados y los modales integrados
    success_response = {
        "allow": True, 
        "welcome_subject": welcome_subject, 
        "welcome_message": welcome_message
    }

    if status_finished and su_status == status_finished:
      return {"allow": False, "message": "La medición ha finalizado."}
      
    if status_in_progress and su_status != status_in_progress:
      if su_start_date:
        start_date_str = get_datetime(su_start_date).strftime("%d/%m/%Y a las %H:%M")
        return {"allow": False, "message": f"Agradecemos tu interés. Esta medición iniciará el {start_date_str}. Te invitamos a regresar a partir de esa fecha para participar."}
      else:
        return {"allow": False, "message": "Agradecemos tu interés. La medición aún no ha iniciado. Te invitamos a regresar más adelante para participar."}
      
    now_local = _now_in_survey_tz_by_su_name(survey_name).replace(tzinfo=None)

    # Validación de inicio de la medición
    if su_start_date:
      if get_datetime(su_start_date) > now_local:
        start_date_str = get_datetime(su_start_date).strftime("%d/%m/%Y a las %H:%M")
        return {"allow": False, "message": f"Agradecemos tu interés. Esta medición iniciará el {start_date_str}. Te invitamos a regresar a partir de esa fecha para participar."}

    # Validación de finalización de la medición
    if su_end_date:
      if get_datetime(su_end_date) <= now_local:
        return {"allow": False, "message": "El enlace ha expirado."}

    if not token or token == "Anonimo":
      # Permitir acceso público si el DNI corresponde a un destinatario registrado
      if dni:
        if survey_name_id:
          recipient_exists = frappe.db.exists(
            "qp_IQ_SurveyRecipient",
            {"sr_survey": survey_name_id, "sr_contact": frappe.db.get_value("Contact", {"custom_document_number": dni}, "name")}
          )
          if recipient_exists:
            return success_response
      return success_response

    secret = _get_jwt_secret()
    try:
      payload = jwt.decode(token, secret, algorithms=["HS256"])
      rid = payload.get("rid")
      sur_claim = payload.get("sur")
      is_public = payload.get("public", False)

      if sur_claim != survey_name:
          return {"allow": False, "message": "Enlace inválido o expirado."}

      survey_end_date = survey_doc.su_end_date
      if survey_end_date:
          if get_datetime(survey_end_date) < now_local:
              return {"allow": False, "message": "El enlace ha expirado."}

      recipients_count = frappe.db.count("qp_IQ_SurveyRecipient", {"sr_survey": survey_name_id}) if survey_name_id else 0

      # Enlace público (genérico)
      if is_public:
        # Si hay destinatarios definidos para la medición, exigir validación por DNI
        if recipients_count > 0 and dni:
          survey_owner_company = survey_doc.su_owner
          if not survey_owner_company:
              return {"allow": False, "message": "No se pudo determinar la empresa propietaria de la encuesta."}

          contact_info = frappe.db.get_value(
              "Contact",
              {"custom_document_number": dni, "custom_company": survey_owner_company},
              ["name", "custom_company", "status"],
              as_dict=True
          )
          public_token = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "su_public_token")

          if not contact_info:
              return {"allow": False, "valid_dni": False, "message": "El DNI proporcionado no corresponde a un contacto registrado.", "redirect_register": True, "register_token": public_token}
          if contact_info.custom_company != survey_owner_company:
              return {"allow": False, "valid_dni": False, "message": "El DNI proporcionado no pertenece a un contacto válido para esta encuesta.", "redirect_register": True, "register_token": public_token}
          if contact_info.status not in ("Enabled", "Passive"):
              return {"allow": False, "valid_dni": False, "message": "El contacto no está activo para responder esta encuesta.", "redirect_register": True, "register_token": public_token}

          recipient_exists = frappe.db.exists(
              "qp_IQ_SurveyRecipient",
              {"sr_survey": survey_name_id, "sr_contact": contact_info.name}
          )
          if recipient_exists:
              return success_response
          else:
              return {"allow": False, "valid_dni": False, "message": "No está habilitado para responder esta encuesta."}

        return success_response

      if not rid:
          public_token = frappe.db.get_value("qp_IQ_Survey", {"su_name": survey_name}, "su_public_token")
          if not dni:
              return {"allow": False, "redirect_register": True, "message": "Debe identificarse para responder esta encuesta.", "register_token": public_token}
              
          survey_owner_company = survey_doc.su_owner
          if not survey_owner_company:
              return {"allow": False, "message": "No se pudo determinar la empresa propietaria de la encuesta."}

          contact_info = frappe.db.get_value(
              "Contact",
              {"custom_document_number": dni, "custom_company": survey_owner_company},
              ["name", "custom_company", "status"],
              as_dict=True
          )

          if not contact_info:
              return {"allow": False, "valid_dni": False, "message": "El DNI proporcionado no corresponde a un contacto registrado.", "redirect_register": True, "register_token": public_token}
          if contact_info.custom_company != survey_owner_company:
              return {"allow": False, "valid_dni": False, "message": "El DNI proporcionado no pertenece a un contacto válido para esta encuesta.", "redirect_register": True, "register_token": public_token}
          if contact_info.status not in ("Enabled", "Passive"):
              return {"allow": False, "valid_dni": False, "message": "El contacto no está activo para responder esta encuesta.", "redirect_register": True, "register_token": public_token}

          contact_name = contact_info.name
          if contact_name and survey_name_id:
              recipient_exists = frappe.db.exists(
                  "qp_IQ_SurveyRecipient",
                  {"sr_survey": survey_name_id, "sr_contact": contact_name}
              )
              if not recipient_exists:
                  return {"allow": False, "valid_dni": False, "message": "No está habilitado para responder esta encuesta."}

              existing_response_by_contact = frappe.db.exists(
                  "Survey Response",
                  {"survey": survey_name, "user": contact_name}
              )
              # Evitar validación directa de completado por nombre/dni si es liderazgo
              if existing_response_by_contact and not is_leadership:
                  return {"allow": False, "message": "Esta encuesta ya fue completada. Gracias por tu participación."}

              existing_recipient = frappe.db.exists(
                  "qp_IQ_SurveyRecipient",
                  {"sr_survey": survey_name_id, "sr_contact": contact_name, "sr_status": rs_responded}
              )
              if existing_recipient and not is_leadership:
                  return {"allow": False, "message": "Esta encuesta ya fue completada. Gracias por tu participación."}

          existing_response = frappe.db.exists(
              "Survey Response",
              {"survey": survey_name, "user": dni}
          )
          if existing_response and not is_leadership:
              return {"allow": False, "message": "Esta encuesta ya fue completada con el DNI proporcionado. Gracias por tu participación."}

      recipient = None
      if rid:
        recipient = frappe.db.get_value(
          "qp_IQ_SurveyRecipient", rid, ["name", "sr_status", "sr_survey", "sr_contact"], as_dict=True
        )
      if not recipient:
        recipient = frappe.db.get_value(
          "qp_IQ_SurveyRecipient", {"sr_token": token}, ["name", "sr_status", "sr_survey", "sr_contact"], as_dict=True
        )

      if rid and not recipient:
        return {"allow": False, "message": "Este enlace ya no es válido. El destinatario fue removido de la medición."}

      if recipient:
        if recipient.get("sr_contact"):
            contact_status = frappe.db.get_value("Contact", recipient.sr_contact, "status")
            if contact_status and contact_status not in ("Enabled", "Passive"):
                return {"allow": False, "message": "El contacto no está activo para responder esta encuesta."}

            dni_from_contact = frappe.db.get_value("Contact", recipient.sr_contact, "custom_document_number")
            if dni_from_contact and not is_leadership:
                existing_response = frappe.db.exists(
                    "Survey Response",
                    {"survey": survey_name, "user": dni_from_contact}
                )
                if existing_response:
                    return {"allow": False, "message": "Esta encuesta ya fue completada con el DNI proporcionado. Gracias por tu participación."}

        su_name_of_recipient = frappe.db.get_value("qp_IQ_Survey", recipient.sr_survey, "su_name")
        if su_name_of_recipient != survey_name:
          return {"allow": False, "message": "Enlace inválido o expirado."}
        if recipient.sr_status == rs_responded:
          return {"allow": False, "message": "Esta encuesta ya fue completada. Gracias por tu participación."}

      return success_response

    except jwt.ExpiredSignatureError:
      return {"allow": False, "message": "El enlace ha expirado."}
    except jwt.InvalidTokenError:
      return {"allow": False, "message": "Enlace inválido o expirado."}
  except Exception:
    frappe.log_error(frappe.get_traceback(), "Error en validate_survey_link")
    return {"allow": True}
  except jwt.InvalidTokenError:
    return {"allow": False, "message": "Enlace inválido o expirado."}

@frappe.whitelist(allow_guest=True)
def get_survey_route_for_public_link(token, dni=None):
    if dni and str(dni).strip().lower() in ["null", "none", "undefined", ""]:
        dni = None
        
    if not token:
        return {"error": "Token no proporcionado."}

    secret = _get_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return {"error": "El enlace ha expirado o no es válido."}

    survey_name = payload.get("sur")
    rid = payload.get("rid")
    
    if not survey_name:
        return {"error": "Token de encuesta inválido."}

    status_finished = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "Finalizada"}, "name")
    status_in_progress = frappe.get_value("qp_IQ_SurveyStatus", {"se_status": "En Progreso"}, "name")
    su_doc = frappe.db.get_value(
        "qp_IQ_Survey", {"su_name": survey_name}, ["name", "su_status", "su_start_date", "su_end_date", "su_is_leadership", "su_owner"], as_dict=True
    )
    if not su_doc:
        return {"error": "Encuesta no encontrada."}
        
    if status_finished and su_doc.su_status == status_finished:
        return {"error": "El enlace ha expirado o la medición ha finalizado."}

    if status_in_progress and su_doc.su_status != status_in_progress:
        if su_doc.su_start_date:
            start_date_str = get_datetime(su_doc.su_start_date).strftime("%d/%m/%Y a las %H:%M")
            return {"error": f"Agradecemos tu interés. Esta medición iniciará el {start_date_str}. Te invitamos a regresar a partir de esa fecha para participar."}
        else:
            return {"error": "Agradecemos tu interés. La medición aún no ha iniciado. Te invitamos a regresar más adelante para participar."}

    now_local = _now_in_survey_tz_by_su_name(survey_name).replace(tzinfo=None)

    if su_doc.su_start_date:
        if get_datetime(su_doc.su_start_date) > now_local:
            start_date_str = get_datetime(su_doc.su_start_date).strftime("%d/%m/%Y a las %H:%M")
            return {"error": f"Agradecemos tu interés. Esta medición iniciará el {start_date_str}. Te invitamos a regresar a partir de esa fecha para participar."}

    if su_doc.su_end_date:
        if get_datetime(su_doc.su_end_date) <= now_local:
            return {"error": "El enlace ha expirado."}

    web_form_route = frappe.db.get_value("Web Form", {"title": survey_name}, "route")
    if not web_form_route:
        return {"error": "No se encontró el formulario para la encuesta."}
        
    if not su_doc.su_is_leadership:
        return {"route": web_form_route, "is_leadership": False, "has_rid": bool(rid)}
        
    # Es medición de Liderazgo (360), buscamos al evaluador
    contact_name = None
    
    # Si tenemos rid, es un enlace personalizado y obtenemos el evaluador directamente
    if rid:
        contact_name = frappe.db.get_value("qp_IQ_SurveyRecipient", rid, "sr_evaluating_to")
        if not contact_name:
            contact_name = frappe.db.get_value("qp_IQ_SurveyRecipient", rid, "sr_contact")
            
    # Si no es personalizado pero hay DNI, buscamos el contacto por su DNI
    if not contact_name and dni:
        contact_name = frappe.db.get_value("Contact", {"custom_document_number": dni, "custom_company": su_doc.su_owner}, "name")
        if not contact_name:
            # En lugar de frappe.throw(), devolvemos un JSON con el error para manejarlo limpiamente en JS
            return {"error": "El DNI proporcionado no corresponde a un contacto registrado."}
            
    # Si no hay ni DNI ni RID, es un enlace genérico y se debe solicitar DNI obligatoriamente en el formulario
    if not contact_name:
        return {"require_dni": True, "is_leadership": True}
        
    rs_responded = frappe.get_value("qp_IQ_RecipientStatus", {"rs_status": "Responded"}, "name") or "Responded"
    
    # Buscamos todas las evaluaciones asignadas a este evaluador
    recipients = frappe.get_all(
        "qp_IQ_SurveyRecipient", 
        filters={"sr_survey": su_doc.name, "sr_evaluating_to": contact_name, "sr_status": ["!=", rs_responded]}, 
        fields=["name", "sr_evaluation_role", "sr_evaluating_to", "sr_contact"]
    )
    
    if not recipients:
        return {"is_completed": True, "message": "Has completado todas tus evaluaciones. ¡Gracias por tu participación!"}
        
    evaluations = []
    for r in recipients:
        c_data = frappe.db.get_value("Contact", r.sr_contact, ["first_name", "last_name"], as_dict=True)
        if c_data:
            evaluatee_name = f"{(c_data.first_name or '').strip()} {(c_data.last_name or '').strip()}".strip()
        else:
            evaluatee_name = r.sr_contact
            
        # Generar un token con el Recipient ID embebido para aperturar esa evaluación específica
        eval_payload = {
            "sur": survey_name,
            "rid": r.name,
            "iat": int(time()),
        }
        eval_token = jwt.encode(eval_payload, secret, algorithm="HS256")
        if isinstance(eval_token, bytes):
            eval_token = eval_token.decode("utf-8")
            
        is_auto = (r.sr_evaluation_role == "Autoevaluación" and r.sr_evaluating_to == r.sr_contact)
        
        evaluations.append({
            "id": r.name,
            "role": r.sr_evaluation_role or "Evaluador",
            "evaluatee_name": evaluatee_name,
            "is_auto": is_auto,
            "token": eval_token
        })
        
    return {"route": web_form_route, "is_leadership": True, "evaluations": evaluations}

def generate_public_link_for_survey_hook(doc, method):

    if doc.su_custom_generate_public_link:
        original_ignore_permissions = frappe.flags.ignore_permissions
        frappe.flags.ignore_permissions = True
        try:
            if generate_public_link_for_survey(doc, method):
                frappe.db.set_value(doc.doctype, doc.name, {
                    "su_public_link": doc.su_public_link,
                    "su_public_token": doc.su_public_token,
                    "su_public_link_created_on": doc.su_public_link_created_on,
                    "su_public_link_created_by": doc.su_public_link_created_by,
                    "su_custom_generate_public_link": 0
                })
            else:
                pass
        finally:
            frappe.flags.ignore_permissions = original_ignore_permissions
    else:
        pass

def generate_public_link_for_survey(doc, method):
    modified = False
    if not doc.su_public_link:
        web_form_route = frappe.db.get_value("Web Form", {"title": doc.su_name}, "route")
        if not web_form_route:
            frappe.log_error(f"No se encontró Web Form para la encuesta {doc.su_name}", "generate_public_link_for_survey")
            return modified

        secret = frappe.conf.get("liseniq_jwt_secret") or frappe.conf.get("encryption_key")
        if not secret:
            frappe.log_error("No se encontró 'liseniq_jwt_secret' ni 'encryption_key' para firmar JWT.", "generate_public_link_for_survey")
            return modified

        payload = {
            "sur": doc.su_name,
            "iat": int(time()),
        }

        if doc.su_is_anonymous:
            payload["public"] = True

        try:
            token = jwt.encode(payload, secret, algorithm="HS256")
            if isinstance(token, bytes):
                token = token.decode("utf-8")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Error generando JWT para enlace público")
            return modified

        if doc.su_is_anonymous:
            base_url = frappe.utils.get_url(web_form_route)
            unique_url = f"{base_url}?new=1"
        else:
            base_url = frappe.utils.get_url('/iq-register')
            unique_url = f"{base_url}?token={token}&uq=true"

        doc.su_public_link = unique_url
        doc.su_public_token = token
        doc.su_public_link_created_on = now()
        doc.su_public_link_created_by = frappe.session.user
        
        if hasattr(doc, 'su_custom_generate_public_link'):
            doc.su_custom_generate_public_link = 0
        
        modified = True
    
    return modified
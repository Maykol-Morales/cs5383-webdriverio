/* Qolqe Wallet - interfaz web.
 * Cada página HTML declara data-pagina en <body>; al cargar se ejecuta su inicializador.
 */
"use strict";

const CLAVE_SESION = "qolqe.sesion";

const sesion = {
  leer() {
    try { return JSON.parse(sessionStorage.getItem(CLAVE_SESION)) || null; } catch { return null; }
  },
  guardar(datos) { sessionStorage.setItem(CLAVE_SESION, JSON.stringify(datos)); },
  limpiar() { sessionStorage.removeItem(CLAVE_SESION); },
  token() { return this.leer()?.access_token; },
  usuario() { return this.leer()?.usuario; },
};

/* ---------- Utilidades ---------- */

const $ = (selector, raiz = document) => raiz.querySelector(selector);
const $$ = (selector, raiz = document) => [...raiz.querySelectorAll(selector)];

function soles(valor) {
  const numero = Number(valor);
  const texto = Math.abs(numero).toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${numero < 0 ? "-" : ""}S/ ${texto}`;
}

function fechaLegible(iso) {
  if (!iso) return "";
  const [fecha, hora] = iso.split("T");
  const [a, m, d] = fecha.split("-");
  return hora ? `${d}/${m}/${a} ${hora.slice(0, 5)}` : `${d}/${m}/${a}`;
}

function fechaISO(fecha) {
  const local = new Date(fecha.getTime() - fecha.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

const NOMBRES_TIPO = {
  TRANSFERENCIA_ENVIADA: "Transferencia enviada",
  TRANSFERENCIA_RECIBIDA: "Transferencia recibida",
  RECARGA: "Recarga",
  PAGO_SERVICIO: "Pago de servicio",
};

function mostrarAlerta(elemento, mensaje, tipo = "error") {
  elemento.className = `alerta ${tipo}`;
  elemento.textContent = mensaje;
  elemento.hidden = false;
}

function ocultar(elemento) { elemento.hidden = true; }

let temporizadorToast;
function toast(mensaje, tipo = "info") {
  let caja = $("#toast");
  if (!caja) {
    caja = document.createElement("div");
    caja.id = "toast";
    caja.dataset.testid = "toast";
    caja.setAttribute("role", "status");
    caja.setAttribute("aria-live", "polite");
    document.body.appendChild(caja);
  }
  caja.className = `toast ${tipo}`;
  caja.textContent = mensaje;
  caja.hidden = false;
  clearTimeout(temporizadorToast);
  temporizadorToast = setTimeout(() => { caja.hidden = true; }, 4000);
}

function bloquear(boton, ocupado, textoOcupado = "Procesando...") {
  if (ocupado) {
    boton.dataset.textoOriginal = boton.textContent;
    boton.textContent = textoOcupado;
    boton.disabled = true;
  } else {
    boton.textContent = boton.dataset.textoOriginal || boton.textContent;
    boton.disabled = false;
  }
}

/* ---------- Cliente de la API ---------- */

async function api(ruta, { metodo = "GET", cuerpo, publico = false } = {}) {
  const cabeceras = { "Accept": "application/json" };
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
  if (!publico && sesion.token()) cabeceras["Authorization"] = `Bearer ${sesion.token()}`;

  let respuesta;
  try {
    respuesta = await fetch(ruta, { method: metodo, headers: cabeceras, body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined });
  } catch {
    return { ok: false, estado: 0, datos: { detail: "No se pudo conectar con el servidor" } };
  }
  if (respuesta.status === 401 && !publico) {
    sesion.limpiar();
    window.location.href = "/login?motivo=sesion";
    return new Promise(() => {});
  }
  const datos = respuesta.status === 204 ? null : await respuesta.json().catch(() => null);
  return { ok: respuesta.ok, estado: respuesta.status, datos };
}

function mensajeDeError(resultado) {
  const datos = resultado.datos || {};
  if (datos.errores?.length) return `${datos.detail}: ${datos.errores.map(e => e.mensaje).join("; ")}`;
  return datos.detail || "Ocurrió un error inesperado";
}

/* ---------- Construcción de elementos y diálogos ---------- */

function h(etiqueta, atributos = {}, ...hijos) {
  const elemento = document.createElement(etiqueta);
  for (const [clave, valor] of Object.entries(atributos)) {
    if (valor === undefined || valor === null || valor === false) continue;
    if (clave === "testid") elemento.dataset.testid = valor;
    else if (clave === "clase") elemento.className = valor;
    else if (clave === "texto") elemento.textContent = valor;
    else if (clave.startsWith("on")) elemento.addEventListener(clave.slice(2), valor);
    else elemento.setAttribute(clave, valor === true ? "" : valor);
  }
  hijos.flat().forEach((hijo) => {
    if (hijo !== null && hijo !== undefined && hijo !== false) elemento.append(hijo instanceof Node ? hijo : String(hijo));
  });
  return elemento;
}

function boton(texto, testid, alPulsar, clase = "secundario") {
  return h("button", { type: "button", clase, testid, texto, onclick: alPulsar });
}

function itemVacio(texto) {
  return h("li", { clase: "texto-suave", testid: "lista-vacia", texto });
}

/** Diálogo de confirmación. Devuelve una promesa con true si el usuario confirma. */
function confirmar(titulo, mensaje, textoBoton = "Confirmar", peligro = false) {
  return new Promise((resolver) => {
    let resuelto = false;
    const cerrar = (valor) => {
      if (resuelto) return;
      resuelto = true;
      dialogo.close();
      dialogo.remove();
      resolver(valor);
    };
    const dialogo = h("dialog", { testid: "dialogo-confirmar", "aria-labelledby": "titulo-confirmar" },
      h("h2", { id: "titulo-confirmar", texto: titulo }),
      h("p", { testid: "confirmar-mensaje", texto: mensaje }),
      h("div", { clase: "acciones" },
        boton(textoBoton, "boton-confirmar-accion", () => cerrar(true), peligro ? "peligro" : ""),
        boton("Cancelar", "boton-cancelar-accion", () => cerrar(false))));
    dialogo.addEventListener("cancel", (evento) => { evento.preventDefault(); cerrar(false); });
    document.body.appendChild(dialogo);
    dialogo.showModal();
  });
}

/**
 * Diálogo con un formulario. `alEnviar(valores)` debe devolver el resultado de api():
 * si falla, el error se muestra dentro del diálogo y este sigue abierto.
 * Devuelve una promesa con los datos de la respuesta, o null si se cancela.
 */
function dialogoFormulario({ titulo, campos, textoBoton = "Guardar", alEnviar }) {
  return new Promise((resolver) => {
    const error = h("div", { role: "alert", hidden: true, testid: "dialogo-error" });
    const controles = {};
    const filas = campos.map((campo) => {
      const id = `dialogo-${campo.id}`;
      let control;
      if (campo.tipo === "select") {
        control = h("select", { id, testid: `input-${campo.id}` },
          campo.opciones.map(([valor, texto]) => h("option", { value: valor, texto })));
        control.value = campo.valor ?? "";
      } else if (campo.tipo === "checkbox") {
        control = h("input", { id, type: "checkbox", testid: `input-${campo.id}` });
        control.checked = Boolean(campo.valor);
        controles[campo.id] = control;
        return h("label", { clase: "campo-check", for: id }, control, ` ${campo.etiqueta}`);
      } else {
        control = h("input", { id, type: campo.tipo || "text", testid: `input-${campo.id}`, inputmode: campo.inputmode,
                               maxlength: campo.maxlength, step: campo.step });
        control.value = campo.valor ?? "";
      }
      controles[campo.id] = control;
      return h("div", { clase: "campo" }, h("label", { for: id, texto: campo.etiqueta }), control,
        campo.ayuda && h("span", { clase: "ayuda", texto: campo.ayuda }));
    });

    let resuelto = false;
    const terminar = (valor) => {
      if (resuelto) return;
      resuelto = true;
      dialogo.close();
      dialogo.remove();
      resolver(valor);
    };
    const enviar = h("button", { type: "submit", testid: "boton-guardar-dialogo", texto: textoBoton });
    const formulario = h("form", { novalidate: true }, filas,
      h("div", { clase: "acciones" }, enviar, boton("Cancelar", "boton-cancelar-dialogo", () => terminar(null))));
    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      ocultar(error);
      const valores = Object.fromEntries(Object.entries(controles).map(([clave, control]) =>
        [clave, control.type === "checkbox" ? control.checked : control.value]));
      bloquear(enviar, true, "Guardando...");
      const resultado = await alEnviar(valores);
      bloquear(enviar, false);
      if (resultado.ok) terminar(resultado.datos ?? true);
      else mostrarAlerta(error, mensajeDeError(resultado));
    });
    const dialogo = h("dialog", { testid: "dialogo-formulario", "aria-labelledby": "titulo-dialogo" },
      h("h2", { id: "titulo-dialogo", texto: titulo }), error, formulario);
    dialogo.addEventListener("cancel", (evento) => { evento.preventDefault(); terminar(null); });
    document.body.appendChild(dialogo);
    dialogo.showModal();
    formulario.querySelector("input, select")?.focus();
  });
}

/** Descarga un archivo de la API (con el token) y lo guarda con el nombre que indica el servidor. */
async function descargar(ruta) {
  const respuesta = await fetch(ruta, { headers: { Authorization: `Bearer ${sesion.token()}` } });
  if (!respuesta.ok) {
    const datos = await respuesta.json().catch(() => ({}));
    return { ok: false, estado: respuesta.status, datos };
  }
  const disposicion = respuesta.headers.get("Content-Disposition") || "";
  const nombre = /filename="([^"]+)"/.exec(disposicion)?.[1] || "movimientos.csv";
  const enlace = h("a", { href: URL.createObjectURL(await respuesta.blob()), download: nombre });
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  return { ok: true, nombre };
}

/** Obtiene todas las páginas de los contactos (la API devuelve 10 por página). */
async function todosLosContactos() {
  const contactos = [];
  for (let pagina = 1; ; pagina += 1) {
    const resultado = await api(`/api/contactos?pagina=${pagina}`);
    if (!resultado.ok) break;
    contactos.push(...resultado.datos.contactos);
    if (pagina >= resultado.datos.total_paginas) break;
  }
  return contactos;
}

/* ---------- Dispositivo de este navegador ---------- */

const CLAVE_DISPOSITIVO = "qolqe.dispositivo";

const dispositivoLocal = {
  leer() {
    try { return JSON.parse(localStorage.getItem(CLAVE_DISPOSITIVO)) || null; } catch { return null; }
  },
  guardar(dispositivo) {
    try { localStorage.setItem(CLAVE_DISPOSITIVO, JSON.stringify({ id: dispositivo.id, nombre: dispositivo.nombre })); } catch { /* sin almacenamiento */ }
  },
  olvidar() {
    try { localStorage.removeItem(CLAVE_DISPOSITIVO); } catch { /* sin almacenamiento */ }
  },
};

/* ---------- Estructura de páginas autenticadas ---------- */

const OPCIONES_MENU = [
  ["inicio", "Inicio"],
  ["transferir", "Transferir"],
  ["recargas", "Recargas"],
  ["servicios", "Pagar servicios"],
  ["historial", "Movimientos"],
  ["contactos", "Contactos"],
  ["solicitudes", "Solicitudes"],
  ["limites", "Límites y alertas"],
  ["seguridad", "Seguridad"],
  ["perfil", "Mi perfil"],
];

function montarMenu(paginaActual) {
  const menu = $("#menu");
  if (!menu) return;
  const usuario = sesion.usuario();
  menu.innerHTML = `
    <div class="marca"><span class="logo">Q</span> Qolqe</div>
    ${OPCIONES_MENU.map(([ruta, texto]) =>
      `<a href="/${ruta}" data-testid="nav-${ruta}" ${ruta === paginaActual ? 'aria-current="page"' : ""}>${texto}</a>`).join("")}
    <div class="pie-menu">
      <div data-testid="usuario-nombre"></div>
      <button type="button" class="secundario" data-testid="boton-cerrar-sesion">Cerrar sesión</button>
    </div>`;
  $("[data-testid=usuario-nombre]", menu).textContent = usuario?.nombres || "";
  $("[data-testid=boton-cerrar-sesion]", menu).addEventListener("click", async () => {
    await api("/api/auth/logout", { metodo: "POST" });
    sesion.limpiar();
    window.location.href = "/login?motivo=salida";
  });
}

function requiereSesion() {
  if (!sesion.token()) {
    window.location.href = "/login";
    return false;
  }
  return true;
}

/* ---------- Páginas públicas ---------- */

const paginas = {};

paginas.login = () => {
  const parametros = new URLSearchParams(location.search);
  const aviso = $("#login-aviso");
  const avisos = {
    sesion: ["Tu sesión expiró o fue cerrada. Vuelve a ingresar.", "info"],
    salida: ["Cerraste sesión correctamente.", "exito"],
    registro: ["Tu cuenta fue creada. Ya puedes ingresar.", "exito"],
    desbloqueo: ["Tu cuenta fue desbloqueada. Ya puedes ingresar.", "exito"],
    cierre: ["Tu cuenta fue cerrada. Gracias por usar Qolqe.", "info"],
  };
  const motivo = avisos[parametros.get("motivo")];
  if (motivo) mostrarAlerta(aviso, motivo[0], motivo[1]);

  const dispositivo = dispositivoLocal.leer();
  if (dispositivo) {
    const etiqueta = $("[data-testid=login-dispositivo]");
    etiqueta.textContent = `Ingresando desde: ${dispositivo.nombre}`;
    etiqueta.hidden = false;
  }

  $("#form-login").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const error = $("#login-error");
    ocultar(error);
    const boton = $("#boton-ingresar");
    bloquear(boton, true, "Ingresando...");
    const cuerpo = { celular: $("#celular").value.trim(), pin: $("#pin").value };
    if (dispositivo) cuerpo.dispositivo_id = dispositivo.id;
    const resultado = await api("/api/auth/login", { metodo: "POST", publico: true, cuerpo });
    bloquear(boton, false);
    if (resultado.ok) {
      sesion.guardar(resultado.datos);
      window.location.href = "/inicio";
    } else {
      mostrarAlerta(error, mensajeDeError(resultado));
      $("#pin").value = "";
      $("#pin").focus();
    }
  });
};

paginas.registro = () => {
  $("#form-registro").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const error = $("#registro-error");
    ocultar(error);
    if ($("#pin").value !== $("#pin-confirmacion").value) {
      mostrarAlerta(error, "Los PIN no coinciden");
      return;
    }
    const boton = $("#boton-registrar");
    bloquear(boton, true, "Creando cuenta...");
    const cuerpo = {
      dni: $("#dni").value.trim(),
      nombres: $("#nombres").value.trim(),
      celular: $("#celular").value.trim(),
      pin: $("#pin").value,
    };
    if ($("#correo").value.trim()) cuerpo.correo = $("#correo").value.trim();
    const resultado = await api("/api/usuarios", { metodo: "POST", publico: true, cuerpo });
    bloquear(boton, false);
    if (resultado.ok) {
      window.location.href = "/login?motivo=registro";
    } else {
      mostrarAlerta(error, mensajeDeError(resultado));
    }
  });
};

paginas.desbloqueo = () => {
  const mensaje = $("#desbloqueo-mensaje");
  $("#form-solicitar").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const boton = $("#boton-solicitar");
    bloquear(boton, true, "Enviando...");
    const resultado = await api("/api/seguridad/desbloqueo/solicitar", {
      metodo: "POST", publico: true, cuerpo: { celular: $("#celular").value.trim() },
    });
    bloquear(boton, false);
    if (resultado.ok) {
      mostrarAlerta(mensaje, resultado.datos.mensaje, "info");
      $("#paso-codigo").hidden = false;
      $("#codigo").focus();
    } else {
      mostrarAlerta(mensaje, mensajeDeError(resultado));
    }
  });
  $("#form-confirmar").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const boton = $("#boton-confirmar");
    bloquear(boton, true, "Validando...");
    const resultado = await api("/api/seguridad/desbloqueo/confirmar", {
      metodo: "POST", publico: true, cuerpo: { celular: $("#celular").value.trim(), codigo: $("#codigo").value.trim() },
    });
    bloquear(boton, false);
    if (resultado.ok) {
      window.location.href = "/login?motivo=desbloqueo";
    } else {
      mostrarAlerta(mensaje, mensajeDeError(resultado));
    }
  });
};

/* ---------- Inicio ---------- */

function filaMovimiento(movimiento) {
  const li = document.createElement("li");
  li.dataset.testid = "movimiento-reciente";
  const izquierda = document.createElement("div");
  const titulo = document.createElement("div");
  titulo.textContent = movimiento.descripcion;
  const detalle = document.createElement("small");
  detalle.className = "texto-suave";
  detalle.textContent = `${NOMBRES_TIPO[movimiento.tipo] || movimiento.tipo} · ${fechaLegible(movimiento.fecha)}`;
  izquierda.append(titulo, detalle);
  const monto = document.createElement("strong");
  monto.className = Number(movimiento.importe) < 0 ? "monto-negativo" : "monto-positivo";
  monto.textContent = soles(movimiento.importe);
  li.append(izquierda, monto);
  return li;
}

paginas.inicio = async () => {
  const usuario = sesion.usuario();
  $("#saludo").textContent = `Hola, ${usuario.nombres.split(" ")[0]}`;

  const valor = $("[data-testid=saldo-valor]");
  let saldoActual = null;
  let oculto = false;
  const pintarSaldo = () => { valor.textContent = oculto ? "S/ ••••••" : soles(saldoActual); };

  $("[data-testid=boton-ocultar-saldo]").addEventListener("click", (evento) => {
    oculto = !oculto;
    evento.currentTarget.textContent = oculto ? "Mostrar saldo" : "Ocultar saldo";
    evento.currentTarget.setAttribute("aria-pressed", String(oculto));
    if (saldoActual !== null) pintarSaldo();
  });

  const [saldo, recientes, solicitudes] = await Promise.all([
    api("/api/cuentas/me/saldo"),
    api("/api/movimientos/recientes?limite=5"),
    api("/api/solicitudes?estado=PENDIENTE"),
  ]);
  if (saldo.ok) {
    saldoActual = saldo.datos.saldo;
    pintarSaldo();
    $("#saldo-actualizado").textContent = `Actualizado: ${fechaLegible(saldo.datos.actualizado_en)}`;
  }
  if (solicitudes.ok && solicitudes.datos.recibidas.length) {
    const insignia = $("[data-testid=solicitudes-pendientes]");
    insignia.textContent = solicitudes.datos.recibidas.length;
    insignia.hidden = false;
  }
  const lista = $("[data-testid=lista-recientes]");
  lista.innerHTML = "";
  if (recientes.ok && recientes.datos.length) {
    recientes.datos.forEach((m) => lista.appendChild(filaMovimiento(m)));
  } else {
    lista.innerHTML = '<li class="texto-suave">Aún no tienes movimientos</li>';
  }
};

/* ---------- Perfil ---------- */

paginas.perfil = async () => {
  const mensaje = $("#perfil-mensaje");

  async function cargar() {
    const resultado = await api("/api/cuentas/me");
    if (!resultado.ok) return;
    const p = resultado.datos;
    $("[data-testid=perfil-nombres]").textContent = p.nombres;
    $("[data-testid=perfil-celular]").textContent = p.celular;
    $("[data-testid=perfil-dni]").textContent = p.dni;
    $("[data-testid=perfil-correo]").textContent = p.correo || "Sin correo";
    $("[data-testid=perfil-creado]").textContent = fechaLegible(p.creado_en);
    $("#nombres").value = p.nombres;
    $("#correo").value = p.correo || "";
    const datosSesion = sesion.leer();
    if (datosSesion) {
      datosSesion.usuario.nombres = p.nombres;
      sesion.guardar(datosSesion);
      $("[data-testid=usuario-nombre]").textContent = p.nombres;
    }
  }

  $("#form-perfil").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultar(mensaje);
    const boton = $("#boton-guardar-perfil");
    bloquear(boton, true, "Guardando...");
    const resultado = await api("/api/cuentas/me", {
      metodo: "PUT", cuerpo: { nombres: $("#nombres").value, correo: $("#correo").value.trim() || null },
    });
    bloquear(boton, false);
    if (!resultado.ok) {
      mostrarAlerta(mensaje, mensajeDeError(resultado));
      return;
    }
    mostrarAlerta(mensaje, "Tus datos fueron actualizados", "exito");
    cargar();
  });

  $("#boton-cerrar-cuenta").addEventListener("click", async () => {
    ocultar($("#cierre-mensaje"));
    const cerrada = await dialogoFormulario({
      titulo: "Cerrar mi cuenta",
      textoBoton: "Cerrar definitivamente",
      campos: [{ id: "pin-cierre", etiqueta: "Confirma con tu PIN", tipo: "password", inputmode: "numeric", maxlength: 4 }],
      alEnviar: (valores) => api("/api/cuentas/me/cierre", { metodo: "POST", cuerpo: { pin: valores["pin-cierre"] } }),
    });
    if (cerrada) {
      sesion.limpiar();
      window.location.href = "/login?motivo=cierre";
    }
  });
  cargar();
};

/* ---------- Transferir ---------- */

paginas.transferir = async () => {
  const formulario = $("#form-transferencia");
  const error = $("#transferencia-error");
  const dialogo = $("#dialogo-confirmacion");
  let tipo = "QOLQE";
  let solicitud = null;

  const seleccionarPestana = (nuevoTipo) => {
    tipo = nuevoTipo;
    $$(".pestanas button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tipo === tipo)));
    $("#grupo-qolqe").hidden = tipo !== "QOLQE";
    $("#grupo-interbancaria").hidden = tipo !== "INTERBANCARIA";
    ocultar(error);
  };
  $$(".pestanas button").forEach((b) => b.addEventListener("click", () => seleccionarPestana(b.dataset.tipo)));

  const selector = $("#contacto");
  (await todosLosContactos()).forEach((c) => {
    selector.appendChild(h("option", { value: c.id, texto: `${c.favorito ? "★ " : ""}${c.alias} (${c.celular})` }));
  });
  const contactoInicial = new URLSearchParams(location.search).get("contacto");
  if (contactoInicial) selector.value = contactoInicial;
  const sincronizarCelular = () => { $("#celular-destino").disabled = Boolean(selector.value); };
  selector.addEventListener("change", sincronizarCelular);
  sincronizarCelular();

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultar(error);
    solicitud = { tipo, monto: $("#monto").value.trim() };
    const descripcion = $("#descripcion").value.trim();
    if (descripcion) solicitud.descripcion = descripcion;
    if (tipo === "QOLQE") {
      if (selector.value) solicitud.contacto_id = Number(selector.value);
      else solicitud.celular_destino = $("#celular-destino").value.trim();
    } else {
      solicitud.cci = $("#cci").value.trim();
    }

    const boton = $("#boton-continuar");
    bloquear(boton, true, "Calculando...");
    const comision = await api(`/api/transferencias/comision?monto=${encodeURIComponent(solicitud.monto)}&tipo=${tipo}`);
    bloquear(boton, false);
    if (!comision.ok) {
      mostrarAlerta(error, mensajeDeError(comision));
      return;
    }
    const destino = tipo === "QOLQE"
      ? (selector.value ? selector.selectedOptions[0].textContent : solicitud.celular_destino)
      : `CCI ${solicitud.cci}`;
    $("[data-testid=confirmar-destino]").textContent = destino;
    $("[data-testid=confirmar-monto]").textContent = soles(comision.datos.monto);
    $("[data-testid=confirmar-comision]").textContent = soles(comision.datos.comision);
    $("[data-testid=confirmar-total]").textContent = soles(comision.datos.total);
    dialogo.showModal();
  });

  $("#boton-cancelar").addEventListener("click", () => dialogo.close());
  $("#boton-confirmar").addEventListener("click", async () => {
    const boton = $("#boton-confirmar");
    bloquear(boton, true, "Transfiriendo...");
    const resultado = await api("/api/transferencias", { metodo: "POST", cuerpo: solicitud });
    bloquear(boton, false);
    dialogo.close();
    if (!resultado.ok) {
      mostrarAlerta(error, mensajeDeError(resultado));
      return;
    }
    const r = resultado.datos;
    $("[data-testid=comprobante-codigo]").textContent = r.codigo_operacion;
    $("[data-testid=comprobante-destino]").textContent = r.destinatario.nombre
      ? `${r.destinatario.nombre} (${r.destinatario.celular})` : `CCI ${r.destinatario.cci}`;
    $("[data-testid=comprobante-monto]").textContent = soles(r.monto);
    $("[data-testid=comprobante-comision]").textContent = soles(r.comision);
    $("[data-testid=comprobante-total]").textContent = soles(r.total);
    $("[data-testid=comprobante-saldo]").textContent = soles(r.saldo);
    $("[data-testid=comprobante-fecha]").textContent = fechaLegible(r.fecha);
    formulario.closest(".tarjeta").hidden = true;
    $("#comprobante").hidden = false;
    toast("Transferencia realizada con éxito");
  });

  $("#boton-nueva").addEventListener("click", () => {
    formulario.reset();
    sincronizarCelular();
    $("#comprobante").hidden = true;
    formulario.closest(".tarjeta").hidden = false;
  });
};

/* ---------- Recargas y recargas programadas ---------- */

const NOMBRES_RESULTADO = { EXITOSA: "Exitosa", FALLIDA: "Fallida", SIN_EJECUCIONES: "Sin ejecuciones" };

paginas.recargas = async () => {
  const formulario = $("#form-recarga");
  const error = $("#recarga-error");
  const configuracion = await api("/api/recargas/configuracion");
  if (!configuracion.ok) return;
  const { montos, bono } = configuracion.datos;

  const contenedor = $("[data-testid=montos-recarga]");
  montos.forEach((monto) => {
    const etiqueta = document.createElement("label");
    etiqueta.innerHTML = `<input type="radio" name="monto" value="${monto}" data-testid="monto-${monto}"><span>S/ ${monto}</span>`;
    contenedor.appendChild(etiqueta);
    $("#prog-monto").appendChild(h("option", { value: monto, texto: `S/ ${monto}` }));
  });
  $("#info-bono").textContent =
    `Recargas desde S/ ${bono.monto_minimo} reciben un bono de ${bono.porcentaje}% (máximo S/ ${bono.tope}).`;

  contenedor.addEventListener("change", () => {
    const monto = Number(formulario.monto.value);
    const vistaPrevia = $("[data-testid=bono-estimado]");
    if (monto >= Number(bono.monto_minimo)) {
      const estimado = Math.min(monto * Number(bono.porcentaje) / 100, Number(bono.tope));
      vistaPrevia.textContent = `Bono estimado: ${soles(estimado)}`;
    } else {
      vistaPrevia.textContent = "Este monto no recibe bono";
    }
  });

  async function cargarHistorial() {
    const lista = $("[data-testid=lista-recargas]");
    const recargas = await api("/api/recargas");
    lista.innerHTML = "";
    if (!recargas.ok || !recargas.datos.length) {
      lista.appendChild(itemVacio("Aún no hiciste recargas"));
      return;
    }
    recargas.datos.forEach((r) => {
      lista.appendChild(h("li", { testid: "recarga" },
        h("div", {},
          h("strong", { texto: `${r.celular} · ${soles(r.monto)}` }), h("br"),
          h("small", { clase: "texto-suave", texto: `Bono ${soles(r.bono)} · ${fechaLegible(r.fecha)}` })),
        h("span", { clase: `etiqueta-estado ${r.origen === "PROGRAMADA" ? "info" : ""}`, testid: "recarga-origen",
                    texto: r.origen === "PROGRAMADA" ? "Programada" : "Manual" })));
    });
  }

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultar(error);
    if (!formulario.monto.value) {
      mostrarAlerta(error, "Selecciona un monto");
      return;
    }
    const boton = $("#boton-recargar");
    bloquear(boton, true, "Recargando...");
    const resultado = await api("/api/recargas", {
      metodo: "POST", cuerpo: { celular: $("#celular").value.trim(), monto: formulario.monto.value },
    });
    bloquear(boton, false);
    if (!resultado.ok) {
      mostrarAlerta(error, mensajeDeError(resultado));
      return;
    }
    const r = resultado.datos;
    $("[data-testid=comprobante-codigo]").textContent = r.codigo_operacion;
    $("[data-testid=comprobante-celular]").textContent = r.celular;
    $("[data-testid=comprobante-monto]").textContent = soles(r.monto);
    $("[data-testid=comprobante-bono]").textContent = soles(r.bono);
    $("[data-testid=comprobante-saldo]").textContent = soles(r.saldo);
    $("[data-testid=comprobante-fecha]").textContent = fechaLegible(r.fecha);
    $("#comprobante").hidden = false;
    toast("Recarga realizada");
    cargarHistorial();
  });

  /* Programadas */
  const errorProgramada = $("#programada-error");

  async function accionProgramada(programada, accion, mensajeExito) {
    const resultado = await api(`/api/recargas/programadas/${programada.id}/${accion}`, { metodo: "POST" });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    toast(mensajeExito);
    cargarProgramadas();
  }

  async function editarProgramada(programada) {
    const editada = await dialogoFormulario({
      titulo: "Editar recarga programada",
      campos: [
        { id: "editar-monto", etiqueta: "Monto", tipo: "select", valor: String(Number(programada.monto)),
          opciones: montos.map((m) => [m, `S/ ${m}`]) },
        { id: "editar-dia", etiqueta: "Día del mes", tipo: "number", valor: programada.dia, ayuda: "Entre 1 y 28" },
        { id: "editar-alias", etiqueta: "Alias", valor: programada.alias || "", ayuda: "Hasta 20 caracteres" },
      ],
      alEnviar: (v) => api(`/api/recargas/programadas/${programada.id}`, {
        metodo: "PUT", cuerpo: { monto: v["editar-monto"], dia: Number(v["editar-dia"]), alias: v["editar-alias"] },
      }),
    });
    if (editada) {
      toast("Recarga programada actualizada");
      cargarProgramadas();
    }
  }

  async function eliminarProgramada(programada) {
    const nombre = programada.alias || programada.celular;
    if (!await confirmar("¿Eliminar recarga programada?", `Ya no se recargará automáticamente "${nombre}". Las recargas realizadas se conservan.`, "Eliminar", true)) return;
    const resultado = await api(`/api/recargas/programadas/${programada.id}`, { metodo: "DELETE" });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    toast("Recarga programada eliminada");
    cargarProgramadas();
  }

  async function cargarProgramadas() {
    const lista = $("[data-testid=lista-programadas]");
    const resultado = await api("/api/recargas/programadas");
    lista.innerHTML = "";
    if (!resultado.ok) return;
    const activas = resultado.datos.filter((p) => p.estado === "ACTIVA").length;
    $("[data-testid=contador-programadas]").textContent = `${activas} de 3 activas`;
    if (!resultado.datos.length) {
      lista.appendChild(itemVacio("No tienes recargas programadas"));
      return;
    }
    resultado.datos.forEach((p) => {
      const pausada = p.estado === "PAUSADA";
      const ultimo = NOMBRES_RESULTADO[p.ultimo_resultado] || p.ultimo_resultado;
      lista.appendChild(h("li", { testid: "programada", "data-id": p.id },
        h("div", {},
          h("strong", { testid: "programada-titulo", texto: `${p.alias ? `${p.alias} · ` : ""}${p.celular} · ${soles(p.monto)}` }), h("br"),
          h("small", { clase: "texto-suave", testid: "programada-detalle",
                       texto: `Día ${p.dia} de cada mes · Próxima: ${pausada ? "en pausa" : fechaLegible(p.proxima_ejecucion)} · Última: ${ultimo}` }),
          p.ultimo_resultado === "FALLIDA" && p.ultimo_detalle
            ? h("small", { clase: "texto-error", testid: "programada-motivo", texto: ` (${p.ultimo_detalle})` }) : null),
        h("div", { clase: "acciones" },
          h("span", { clase: `etiqueta-estado ${pausada ? "advertencia" : "exito"}`, testid: "programada-estado", texto: pausada ? "Pausada" : "Activa" }),
          boton("Editar", "boton-editar-programada", () => editarProgramada(p)),
          pausada
            ? boton("Reanudar", "boton-reanudar-programada", () => accionProgramada(p, "reanudar", "Recarga programada reanudada"))
            : boton("Pausar", "boton-pausar-programada", () => accionProgramada(p, "pausar", "Recarga programada pausada")),
          boton("Eliminar", "boton-eliminar-programada", () => eliminarProgramada(p), "peligro"))));
    });
  }

  $("#form-programada").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultar(errorProgramada);
    const cuerpo = {
      celular: $("#prog-celular").value.trim(),
      monto: $("#prog-monto").value,
      dia: Number($("#prog-dia").value),
    };
    if ($("#prog-alias").value.trim()) cuerpo.alias = $("#prog-alias").value;
    const boton = $("#boton-programar");
    bloquear(boton, true, "Programando...");
    const resultado = await api("/api/recargas/programadas", { metodo: "POST", cuerpo });
    bloquear(boton, false);
    if (!resultado.ok) {
      mostrarAlerta(errorProgramada, mensajeDeError(resultado));
      return;
    }
    evento.target.reset();
    toast(`Recarga programada. Próxima ejecución: ${fechaLegible(resultado.datos.proxima_ejecucion)}`);
    cargarProgramadas();
  });

  cargarHistorial();
  cargarProgramadas();
};

/* ---------- Pago de servicios y afiliaciones ---------- */

const NOMBRES_SITUACION = { AL_DIA: "Al día", CON_DEUDA: "Con deuda", EN_COBRANZA: "En cobranza" };

paginas.servicios = async () => {
  const error = $("#servicios-error");
  const dialogo = $("#dialogo-pago");
  let deudaSeleccionada = null;

  const empresas = await api("/api/servicios/empresas");
  if (empresas.ok) {
    empresas.datos.forEach((e) => {
      $("#empresa").appendChild(h("option", { value: e.codigo, texto: `${e.nombre} (${e.rubro})` }));
      $("#afi-empresa").appendChild(h("option", { value: e.codigo, texto: `${e.nombre} (${e.rubro})` }));
    });
  }

  function tarjetaDeuda(deuda) {
    const li = document.createElement("li");
    li.dataset.testid = "deuda";
    const info = document.createElement("div");
    info.innerHTML = `<strong></strong><br><small class="texto-suave"></small>`;
    info.querySelector("strong").textContent = `Periodo ${deuda.periodo} · ${deuda.titular}`;
    const detalle = deuda.estado === "EN_COBRANZA"
      ? `Vencida el ${fechaLegible(deuda.vencimiento)} · En cobranza`
      : `Vence: ${fechaLegible(deuda.vencimiento)} · Monto ${soles(deuda.monto)} · Mora ${soles(deuda.mora)}`;
    info.querySelector("small").textContent = detalle;
    const acciones = document.createElement("div");
    if (deuda.estado === "EN_COBRANZA") {
      acciones.innerHTML = '<span class="alerta error" data-testid="deuda-cobranza">En cobranza</span>';
    } else {
      const total = document.createElement("strong");
      total.dataset.testid = "deuda-total";
      total.textContent = soles(deuda.total);
      const botonPagar = boton("Pagar", "boton-pagar-deuda", () => {
        deudaSeleccionada = deuda;
        $("[data-testid=pago-detalle]").textContent = `${deuda.empresa} · Suministro ${deuda.suministro} · Periodo ${deuda.periodo}`;
        $("[data-testid=pago-total]").textContent = soles(deuda.total);
        dialogo.showModal();
      }, "");
      acciones.className = "acciones";
      acciones.append(total, botonPagar);
    }
    li.append(info, acciones);
    return li;
  }

  async function consultar() {
    ocultar(error);
    $("#comprobante").hidden = true;
    const lista = $("[data-testid=lista-deudas]");
    lista.innerHTML = "";
    const botonConsultar = $("#boton-consultar");
    bloquear(botonConsultar, true, "Consultando...");
    const resultado = await api(`/api/servicios/deudas?empresa=${encodeURIComponent($("#empresa").value)}&suministro=${encodeURIComponent($("#suministro").value.trim())}`);
    bloquear(botonConsultar, false);
    if (!resultado.ok) {
      mostrarAlerta(error, mensajeDeError(resultado), resultado.estado === 404 ? "info" : "error");
      return;
    }
    resultado.datos.forEach((d) => lista.appendChild(tarjetaDeuda(d)));
  }

  function mostrarComprobante(r) {
    $("[data-testid=comprobante-codigo]").textContent = r.codigo_operacion;
    $("[data-testid=comprobante-empresa]").textContent = r.empresa;
    $("[data-testid=comprobante-suministro]").textContent = r.suministro;
    $("[data-testid=comprobante-periodo]").textContent = r.periodo;
    $("[data-testid=comprobante-monto]").textContent = soles(r.monto);
    $("[data-testid=comprobante-mora]").textContent = soles(r.mora);
    $("[data-testid=comprobante-total]").textContent = soles(r.total);
    $("[data-testid=comprobante-saldo]").closest("dd").previousElementSibling.hidden = !r.saldo;
    $("[data-testid=comprobante-saldo]").hidden = !r.saldo;
    $("[data-testid=comprobante-saldo]").textContent = r.saldo ? soles(r.saldo) : "";
    $("#comprobante").hidden = false;
    $("#comprobante").scrollIntoView({ behavior: "smooth", block: "center" });
  }

  $("#form-consulta").addEventListener("submit", (evento) => { evento.preventDefault(); consultar(); });
  $("#boton-cancelar-pago").addEventListener("click", () => dialogo.close());
  $("#boton-confirmar-pago").addEventListener("click", async () => {
    const botonPago = $("#boton-confirmar-pago");
    bloquear(botonPago, true, "Pagando...");
    const resultado = await api("/api/servicios/pagos", { metodo: "POST", cuerpo: { deuda_id: deudaSeleccionada.id } });
    bloquear(botonPago, false);
    dialogo.close();
    if (!resultado.ok) {
      mostrarAlerta(error, mensajeDeError(resultado));
      return;
    }
    $("[data-testid=lista-deudas]").innerHTML = "";
    mostrarComprobante(resultado.datos);
    toast("Pago realizado con éxito");
    cargarAfiliaciones();
    cargarPagos();
  });

  /* Afiliaciones */
  const errorAfiliacion = $("#afiliacion-error");

  async function cambiarDebito(afiliacion) {
    const activar = !afiliacion.debito_automatico;
    const mensaje = activar
      ? `Pagaremos automáticamente las deudas de "${afiliacion.alias}" el día de su vencimiento.`
      : `Dejaremos de pagar automáticamente las deudas de "${afiliacion.alias}".`;
    if (!await confirmar(activar ? "¿Activar débito automático?" : "¿Desactivar débito automático?", mensaje,
                         activar ? "Activar" : "Desactivar")) return;
    const resultado = await api(`/api/servicios/afiliaciones/${afiliacion.id}`, { metodo: "PUT", cuerpo: { debito_automatico: activar } });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    toast(activar ? "Débito automático activado" : "Débito automático desactivado");
    cargarAfiliaciones();
  }

  async function editarAfiliacion(afiliacion) {
    const editada = await dialogoFormulario({
      titulo: "Editar servicio afiliado",
      campos: [{ id: "editar-alias", etiqueta: "Alias", valor: afiliacion.alias, ayuda: "Entre 3 y 20 caracteres" }],
      alEnviar: (v) => api(`/api/servicios/afiliaciones/${afiliacion.id}`, { metodo: "PUT", cuerpo: { alias: v["editar-alias"] } }),
    });
    if (editada) {
      toast("Servicio actualizado");
      cargarAfiliaciones();
    }
  }

  async function desafiliar(afiliacion) {
    if (!await confirmar("¿Desafiliar servicio?", `Se eliminará "${afiliacion.alias}" de tus servicios. Tus pagos se conservan.`, "Desafiliar", true)) return;
    const resultado = await api(`/api/servicios/afiliaciones/${afiliacion.id}`, { metodo: "DELETE" });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    toast("Servicio desafiliado");
    cargarAfiliaciones();
    cargarPagos();
  }

  async function cargarAfiliaciones() {
    const lista = $("[data-testid=lista-afiliaciones]");
    const filtro = $("#filtro-pagos");
    const seleccion = filtro.value;
    const resultado = await api("/api/servicios/afiliaciones");
    lista.innerHTML = "";
    filtro.length = 1;
    if (!resultado.ok) return;
    $("[data-testid=contador-afiliaciones]").textContent = `${resultado.datos.length} de 8`;
    if (!resultado.datos.length) lista.appendChild(itemVacio("Aún no afiliaste servicios"));
    resultado.datos.forEach((a) => {
      filtro.appendChild(h("option", { value: a.id, texto: a.alias }));
      const claseSituacion = { AL_DIA: "exito", CON_DEUDA: "advertencia", EN_COBRANZA: "error" }[a.situacion];
      lista.appendChild(h("li", { testid: "afiliacion", "data-id": a.id },
        h("div", {},
          h("strong", { testid: "afiliacion-alias", texto: a.alias }), " ",
          h("span", { clase: `etiqueta-estado ${claseSituacion}`, testid: "afiliacion-situacion", texto: NOMBRES_SITUACION[a.situacion] }), h("br"),
          h("small", { clase: "texto-suave", testid: "afiliacion-detalle",
                       texto: `${a.empresa_nombre} · ${a.suministro} · Pendiente ${soles(a.total_pendiente)}`
                         + (a.proximo_vencimiento ? ` · Próximo vencimiento ${fechaLegible(a.proximo_vencimiento)}` : "") }), h("br"),
          h("small", { testid: "afiliacion-debito", texto: `Débito automático: ${a.debito_automatico ? "activado" : "desactivado"}` })),
        h("div", { clase: "acciones" },
          boton("Consultar", "boton-consultar-afiliacion", () => {
            $("#empresa").value = a.empresa;
            $("#suministro").value = a.suministro;
            consultar();
            $("#form-consulta").scrollIntoView({ behavior: "smooth" });
          }, ""),
          boton(a.debito_automatico ? "Desactivar débito" : "Activar débito", "boton-debito-afiliacion", () => cambiarDebito(a)),
          boton("Editar", "boton-editar-afiliacion", () => editarAfiliacion(a)),
          boton("Desafiliar", "boton-desafiliar", () => desafiliar(a), "peligro"))));
    });
    if ([...filtro.options].some((o) => o.value === seleccion)) filtro.value = seleccion;
  }

  async function cargarPagos() {
    const lista = $("[data-testid=lista-pagos]");
    const filtro = $("#filtro-pagos").value;
    const resultado = await api(`/api/servicios/pagos${filtro ? `?afiliacion_id=${filtro}` : ""}`);
    lista.innerHTML = "";
    if (!resultado.ok) return;
    if (!resultado.datos.length) lista.appendChild(itemVacio("No hay pagos para mostrar"));
    resultado.datos.forEach((p) => {
      lista.appendChild(h("li", { testid: "pago", "data-codigo": p.codigo_operacion },
        h("div", {},
          h("strong", { texto: `${p.empresa} · ${p.suministro} · ${p.periodo}` }), h("br"),
          h("small", { clase: "texto-suave",
                       texto: `${fechaLegible(p.fecha)} · ${p.origen === "DEBITO_AUTOMATICO" ? "Débito automático" : "Pago manual"}` })),
        h("div", { clase: "acciones" },
          h("strong", { texto: soles(p.total) }),
          boton("Ver comprobante", "boton-ver-comprobante", async () => {
            const detalle = await api(`/api/servicios/pagos/${encodeURIComponent(p.codigo_operacion)}`);
            if (detalle.ok) mostrarComprobante(detalle.datos);
            else toast(mensajeDeError(detalle), "error");
          }))));
    });
  }

  $("#filtro-pagos").addEventListener("change", cargarPagos);
  $("#form-afiliacion").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultar(errorAfiliacion);
    const botonAfiliar = $("#boton-afiliar");
    bloquear(botonAfiliar, true, "Afiliando...");
    const resultado = await api("/api/servicios/afiliaciones", {
      metodo: "POST",
      cuerpo: { empresa: $("#afi-empresa").value, suministro: $("#afi-suministro").value.trim(), alias: $("#afi-alias").value },
    });
    bloquear(botonAfiliar, false);
    if (!resultado.ok) {
      mostrarAlerta(errorAfiliacion, mensajeDeError(resultado));
      return;
    }
    evento.target.reset();
    toast(`Servicio "${resultado.datos.alias}" afiliado`);
    cargarAfiliaciones();
  });

  await cargarAfiliaciones();
  cargarPagos();
};

/* ---------- Historial y categorías ---------- */

const PALETA_COLORES = ["#E53935", "#FB8C00", "#FDD835", "#43A047", "#00897B", "#1E88E5", "#8E24AA", "#6D4C41"];

function chipCategoria(categoria) {
  if (!categoria) return h("span", { clase: "texto-suave", texto: "—" });
  return h("span", { clase: "chip-categoria", testid: "chip-categoria" },
    h("span", { clase: "punto-color", style: `background:${categoria.color}` }), categoria.nombre);
}

function selectorDeColor(contenedor, nombreGrupo, seleccionado = PALETA_COLORES[0]) {
  contenedor.innerHTML = "";
  PALETA_COLORES.forEach((color, indice) => {
    const entrada = h("input", { type: "radio", name: nombreGrupo, value: color, testid: `color-${indice + 1}`, "aria-label": color });
    entrada.checked = color === seleccionado;
    contenedor.appendChild(h("label", { clase: "muestra-color", style: `--color:${color}`, title: color }, entrada, h("span")));
  });
}

paginas.historial = async () => {
  const error = $("#historial-error");
  const hoy = new Date();
  const hace30 = new Date(hoy.getTime() - 30 * 86400000);
  $("#desde").value = fechaISO(hace30);
  $("#hasta").value = fechaISO(hoy);
  let pagina = 1;
  let categorias = [];
  let movimientoActual = null;

  function parametrosFiltro() {
    const parametros = new URLSearchParams({ desde: $("#desde").value, hasta: $("#hasta").value });
    if ($("#tipo").value) parametros.set("tipo", $("#tipo").value);
    if ($("#filtro-categoria").value) parametros.set("categoria_id", $("#filtro-categoria").value);
    return parametros;
  }

  async function buscar() {
    ocultar(error);
    $("#detalle-movimiento").hidden = true;
    const parametros = parametrosFiltro();
    parametros.set("pagina", pagina);
    const cuerpo = $("[data-testid=tabla-movimientos] tbody");
    cuerpo.innerHTML = '<tr><td colspan="5"><span class="esqueleto"></span></td></tr>';
    const resultado = await api(`/api/movimientos?${parametros}`);
    cuerpo.innerHTML = "";
    if (!resultado.ok) {
      mostrarAlerta(error, mensajeDeError(resultado));
      $("#indicador-pagina").textContent = "";
      return;
    }
    const datos = resultado.datos;
    if (!datos.movimientos.length) {
      cuerpo.innerHTML = '<tr><td colspan="5" class="texto-suave" data-testid="sin-movimientos">No hay movimientos en el rango seleccionado</td></tr>';
    }
    datos.movimientos.forEach((m) => {
      const fila = h("tr", { testid: "fila-movimiento", "data-codigo": m.codigo_operacion, onclick: () => verDetalle(m.codigo_operacion) },
        h("td", { texto: fechaLegible(m.fecha) }),
        h("td", { texto: NOMBRES_TIPO[m.tipo] || m.tipo }),
        h("td", {}, m.descripcion, m.nota ? h("br") : null, m.nota ? h("small", { clase: "texto-suave", testid: "movimiento-nota", texto: m.nota }) : null),
        h("td", {}, chipCategoria(m.categoria)),
        h("td", { clase: `numero ${Number(m.importe) < 0 ? "monto-negativo" : "monto-positivo"}`, texto: soles(m.importe) }));
      cuerpo.appendChild(fila);
    });
    $("#indicador-pagina").textContent = `Página ${datos.pagina} de ${datos.total_paginas} · ${datos.total} movimientos`;
    $("#boton-anterior").disabled = datos.pagina <= 1;
    $("#boton-siguiente").disabled = datos.pagina >= datos.total_paginas;
  }

  async function verDetalle(codigo) {
    const resultado = await api(`/api/movimientos/${encodeURIComponent(codigo)}`);
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    const m = resultado.datos;
    movimientoActual = m;
    $("[data-testid=detalle-codigo]").textContent = m.codigo_operacion;
    $("[data-testid=detalle-fecha]").textContent = fechaLegible(m.fecha);
    $("[data-testid=detalle-tipo]").textContent = NOMBRES_TIPO[m.tipo] || m.tipo;
    $("[data-testid=detalle-descripcion]").textContent = m.descripcion;
    $("[data-testid=detalle-monto]").textContent = soles(m.monto);
    $("[data-testid=detalle-comision]").textContent = soles(m.comision);
    $("[data-testid=detalle-importe]").textContent = soles(m.importe);
    $("[data-testid=detalle-contraparte]").textContent = m.contraparte || "—";
    $("#clasificar-categoria").value = m.categoria ? String(m.categoria.id) : "";
    $("#clasificar-nota").value = m.nota || "";
    ocultar($("#clasificar-mensaje"));
    $("#detalle-movimiento").hidden = false;
    $("#detalle-movimiento").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  $("#form-clasificar").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const mensaje = $("#clasificar-mensaje");
    ocultar(mensaje);
    const categoria = $("#clasificar-categoria").value;
    const resultado = await api(`/api/movimientos/${encodeURIComponent(movimientoActual.codigo_operacion)}/clasificacion`, {
      metodo: "PUT", cuerpo: { categoria_id: categoria ? Number(categoria) : null, nota: $("#clasificar-nota").value },
    });
    if (!resultado.ok) {
      mostrarAlerta(mensaje, mensajeDeError(resultado));
      return;
    }
    mostrarAlerta(mensaje, "Clasificación guardada", "exito");
    await cargarCategorias();
    await buscar();
    verDetalle(movimientoActual.codigo_operacion);
  });

  $("#boton-exportar").addEventListener("click", async () => {
    ocultar(error);
    const botonExportar = $("#boton-exportar");
    bloquear(botonExportar, true, "Exportando...");
    const resultado = await descargar(`/api/movimientos/exportar?${parametrosFiltro()}`);
    bloquear(botonExportar, false);
    if (resultado.ok) toast(`Se descargó ${resultado.nombre}`);
    else mostrarAlerta(error, mensajeDeError(resultado));
  });

  /* Categorías */
  const errorCategoria = $("#categoria-error");
  selectorDeColor($("[data-testid=paleta-colores]"), "color-categoria");

  async function editarCategoria(categoria) {
    const campos = [
      { id: "editar-nombre", etiqueta: "Nombre", valor: categoria.nombre, ayuda: "Entre 3 y 20 caracteres" },
      { id: "editar-color", etiqueta: "Color", tipo: "select", valor: categoria.color, opciones: PALETA_COLORES.map((c) => [c, c]) },
    ];
    const editada = await dialogoFormulario({
      titulo: "Editar categoría",
      campos,
      alEnviar: (v) => api(`/api/categorias/${categoria.id}`, { metodo: "PUT", cuerpo: { nombre: v["editar-nombre"], color: v["editar-color"] } }),
    });
    if (editada) {
      toast("Categoría actualizada");
      await cargarCategorias();
      buscar();
    }
  }

  async function eliminarCategoria(categoria) {
    const mensaje = `Los ${categoria.cantidad_movimientos} movimientos de "${categoria.nombre}" quedarán sin categoría.`;
    if (!await confirmar("¿Eliminar categoría?", mensaje, "Eliminar", true)) return;
    const resultado = await api(`/api/categorias/${categoria.id}`, { metodo: "DELETE" });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    toast("Categoría eliminada");
    await cargarCategorias();
    buscar();
  }

  async function cargarCategorias() {
    const resultado = await api("/api/categorias");
    if (!resultado.ok) return;
    categorias = resultado.datos;
    $("[data-testid=contador-categorias]").textContent = `${categorias.length} de 10`;
    for (const selector of [$("#filtro-categoria"), $("#clasificar-categoria")]) {
      const seleccion = selector.value;
      selector.length = 1;
      categorias.forEach((c) => selector.appendChild(h("option", { value: c.id, texto: c.nombre })));
      if ([...selector.options].some((o) => o.value === seleccion)) selector.value = seleccion;
    }
    const lista = $("[data-testid=lista-categorias]");
    lista.innerHTML = "";
    if (!categorias.length) lista.appendChild(itemVacio("Aún no creaste categorías"));
    categorias.forEach((c) => {
      lista.appendChild(h("li", { testid: "categoria", "data-id": c.id },
        h("div", {}, chipCategoria(c), " ",
          h("small", { clase: "texto-suave", testid: "categoria-cantidad", texto: `${c.cantidad_movimientos} movimientos` })),
        h("div", { clase: "acciones" },
          boton("Editar", "boton-editar-categoria", () => editarCategoria(c)),
          boton("Eliminar", "boton-eliminar-categoria", () => eliminarCategoria(c), "peligro"))));
    });
  }

  $("#form-categoria").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultar(errorCategoria);
    const color = $("input[name=color-categoria]:checked")?.value;
    const resultado = await api("/api/categorias", { metodo: "POST", cuerpo: { nombre: $("#categoria-nombre").value, color } });
    if (!resultado.ok) {
      mostrarAlerta(errorCategoria, mensajeDeError(resultado));
      return;
    }
    $("#categoria-nombre").value = "";
    toast(`Categoría "${resultado.datos.nombre}" creada`);
    cargarCategorias();
  });

  $("#form-filtros").addEventListener("submit", (evento) => { evento.preventDefault(); pagina = 1; buscar(); });
  $("#boton-anterior").addEventListener("click", () => { pagina -= 1; buscar(); });
  $("#boton-siguiente").addEventListener("click", () => { pagina += 1; buscar(); });
  await cargarCategorias();
  buscar();
};

/* ---------- Contactos ---------- */

async function solicitarDineroA(contacto) {
  const creada = await dialogoFormulario({
    titulo: `Solicitar dinero a ${contacto.alias}`,
    textoBoton: "Enviar solicitud",
    campos: [
      { id: "solicitud-monto", etiqueta: "Monto (S/)", inputmode: "decimal" },
      { id: "solicitud-motivo", etiqueta: "Motivo", ayuda: "Entre 3 y 60 caracteres" },
    ],
    alEnviar: (v) => api("/api/solicitudes", {
      metodo: "POST", cuerpo: { contacto_id: contacto.id, monto: v["solicitud-monto"].trim(), motivo: v["solicitud-motivo"] },
    }),
  });
  if (creada) toast(`Solicitud enviada. Vence el ${fechaLegible(creada.vence_en)}`);
}

paginas.contactos = async () => {
  const error = $("#contactos-error");
  let pagina = 1;
  let temporizadorBusqueda;

  async function editar(contacto) {
    const editado = await dialogoFormulario({
      titulo: "Editar contacto",
      campos: [
        { id: "nuevo-alias", etiqueta: "Alias", valor: contacto.alias, ayuda: "Entre 3 y 20 caracteres" },
        { id: "favorito", etiqueta: "Marcar como favorito", tipo: "checkbox", valor: contacto.favorito },
      ],
      alEnviar: (v) => api(`/api/contactos/${contacto.id}`, { metodo: "PUT", cuerpo: { alias: v["nuevo-alias"], favorito: v.favorito } }),
    });
    if (editado) {
      toast("Contacto actualizado");
      cargar();
    }
  }

  async function alternarFavorito(contacto) {
    const resultado = await api(`/api/contactos/${contacto.id}`, { metodo: "PUT", cuerpo: { favorito: !contacto.favorito } });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    toast(resultado.datos.favorito ? `${contacto.alias} ahora es favorito` : `${contacto.alias} ya no es favorito`);
    cargar();
  }

  async function eliminar(contacto) {
    if (!await confirmar("¿Eliminar contacto?", `Se eliminará a "${contacto.alias}" de tus contactos.`, "Eliminar", true)) return;
    const resultado = await api(`/api/contactos/${contacto.id}`, { metodo: "DELETE" });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    toast("Contacto eliminado");
    cargar();
  }

  async function cargar() {
    const lista = $("[data-testid=lista-contactos]");
    const parametros = new URLSearchParams({ pagina });
    if ($("#buscar").value.trim()) parametros.set("buscar", $("#buscar").value.trim());
    const resultado = await api(`/api/contactos?${parametros}`);
    lista.innerHTML = "";
    if (!resultado.ok) return;
    const datos = resultado.datos;
    if (pagina > datos.total_paginas) {
      pagina = datos.total_paginas;
      cargar();
      return;
    }
    $("#contador-contactos").textContent = datos.buscar ? `${datos.total} encontrados` : `${datos.total} de 15 contactos`;
    $("#contactos-pagina").textContent = `Página ${datos.pagina} de ${datos.total_paginas}`;
    $("#contactos-anterior").disabled = datos.pagina <= 1;
    $("#contactos-siguiente").disabled = datos.pagina >= datos.total_paginas;
    if (!datos.contactos.length) {
      lista.appendChild(itemVacio(datos.buscar ? "Ningún contacto coincide con la búsqueda" : "Aún no tienes contactos"));
      return;
    }
    datos.contactos.forEach((c) => {
      lista.appendChild(h("li", { testid: "contacto", "data-id": c.id },
        h("div", { clase: "fila-contacto" },
          h("button", { type: "button", clase: `estrella ${c.favorito ? "activa" : ""}`, testid: "boton-favorito",
                        "aria-pressed": String(c.favorito), "aria-label": c.favorito ? "Quitar de favoritos" : "Marcar como favorito",
                        texto: c.favorito ? "★" : "☆", onclick: () => alternarFavorito(c) }),
          h("div", {},
            h("strong", { testid: "contacto-alias", texto: c.alias }), h("br"),
            h("small", { clase: "texto-suave", testid: "contacto-detalle", texto: `${c.nombre} · ${c.celular}` }))),
        h("div", { clase: "acciones" },
          h("a", { clase: "boton", href: `/transferir?contacto=${c.id}`, testid: "boton-transferir-contacto", texto: "Transferir" }),
          boton("Solicitar", "boton-solicitar-contacto", () => solicitarDineroA(c)),
          boton("Editar", "boton-editar-contacto", () => editar(c)),
          boton("Eliminar", "boton-eliminar-contacto", () => eliminar(c), "peligro"))));
    });
  }

  $("#form-contacto").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultar(error);
    const botonAgregar = $("#boton-agregar");
    bloquear(botonAgregar, true, "Agregando...");
    const resultado = await api("/api/contactos", {
      metodo: "POST", cuerpo: { celular: $("#celular").value.trim(), alias: $("#alias").value },
    });
    bloquear(botonAgregar, false);
    if (!resultado.ok) {
      mostrarAlerta(error, mensajeDeError(resultado));
      return;
    }
    evento.target.reset();
    toast(`Contacto "${resultado.datos.alias}" agregado`);
    cargar();
  });

  $("#buscar").addEventListener("input", () => {
    clearTimeout(temporizadorBusqueda);
    temporizadorBusqueda = setTimeout(() => { pagina = 1; cargar(); }, 300);
  });
  $("#contactos-anterior").addEventListener("click", () => { pagina -= 1; cargar(); });
  $("#contactos-siguiente").addEventListener("click", () => { pagina += 1; cargar(); });
  cargar();
};

/* ---------- Solicitudes de dinero ---------- */

const NOMBRES_ESTADO_SOLICITUD = {
  PENDIENTE: ["Pendiente", "advertencia"],
  ACEPTADA: ["Aceptada", "exito"],
  RECHAZADA: ["Rechazada", "error"],
  CANCELADA: ["Cancelada", ""],
  VENCIDA: ["Vencida", ""],
};

paginas.solicitudes = async () => {
  const mensaje = $("#solicitud-mensaje");
  let vista = "recibidas";

  (await todosLosContactos()).forEach((c) => {
    $("#sol-contacto").appendChild(h("option", { value: c.id, texto: `${c.alias} (${c.celular})` }));
  });

  async function aceptar(solicitud) {
    const texto = `Se transferirán ${soles(solicitud.monto)} a ${solicitud.solicitante.nombre} (${solicitud.solicitante.celular}) por "${solicitud.motivo}".`;
    if (!await confirmar("¿Aceptar la solicitud?", texto, "Aceptar y transferir")) return;
    const resultado = await api(`/api/solicitudes/${solicitud.id}/aceptar`, { metodo: "POST" });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      cargar();
      return;
    }
    toast(`Transferencia realizada. Operación ${resultado.datos.codigo_operacion}`);
    cargar();
  }

  async function rechazar(solicitud) {
    const rechazada = await dialogoFormulario({
      titulo: "Rechazar solicitud",
      textoBoton: "Rechazar",
      campos: [{ id: "motivo-rechazo", etiqueta: "Motivo (opcional)", ayuda: "Hasta 60 caracteres" }],
      alEnviar: (v) => api(`/api/solicitudes/${solicitud.id}/rechazar`, {
        metodo: "POST", cuerpo: v["motivo-rechazo"].trim() ? { motivo: v["motivo-rechazo"] } : {},
      }),
    });
    if (rechazada) {
      toast("Solicitud rechazada");
      cargar();
    }
  }

  async function cancelar(solicitud) {
    if (!await confirmar("¿Cancelar la solicitud?", `Se cancelará tu solicitud de ${soles(solicitud.monto)} por "${solicitud.motivo}".`, "Cancelar solicitud", true)) return;
    const resultado = await api(`/api/solicitudes/${solicitud.id}/cancelar`, { metodo: "POST" });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      cargar();
      return;
    }
    toast("Solicitud cancelada");
    cargar();
  }

  function itemSolicitud(s) {
    const recibida = vista === "recibidas";
    const otro = recibida ? s.solicitante : s.destinatario;
    const [estado, clase] = NOMBRES_ESTADO_SOLICITUD[s.estado] || [s.estado, ""];
    const detalle = s.estado === "PENDIENTE" ? `Vence el ${fechaLegible(s.vence_en)}`
      : s.estado === "ACEPTADA" ? `Operación ${s.codigo_operacion}`
      : s.estado === "RECHAZADA" && s.motivo_rechazo ? `Motivo: ${s.motivo_rechazo}`
      : s.resuelta_en ? `El ${fechaLegible(s.resuelta_en)}` : `Venció el ${fechaLegible(s.vence_en)}`;
    const acciones = h("div", { clase: "acciones" },
      h("strong", { testid: "solicitud-monto", texto: soles(s.monto) }),
      h("span", { clase: `etiqueta-estado ${clase}`, testid: "solicitud-estado", texto: estado }));
    if (s.estado === "PENDIENTE" && recibida) {
      acciones.append(boton("Aceptar", "boton-aceptar-solicitud", () => aceptar(s), ""),
                      boton("Rechazar", "boton-rechazar-solicitud", () => rechazar(s), "peligro"));
    }
    if (s.estado === "PENDIENTE" && !recibida) {
      acciones.append(boton("Cancelar", "boton-cancelar-solicitud", () => cancelar(s), "peligro"));
    }
    return h("li", { testid: "solicitud", "data-id": s.id },
      h("div", {},
        h("strong", { testid: "solicitud-motivo", texto: s.motivo }), h("br"),
        h("small", { clase: "texto-suave", testid: "solicitud-persona",
                     texto: `${recibida ? "De" : "Para"} ${otro.nombre} (${otro.celular}) · ${fechaLegible(s.creada_en)}` }), h("br"),
        h("small", { clase: "texto-suave", testid: "solicitud-detalle", texto: detalle })),
      acciones);
  }

  async function cargar() {
    const estado = $("#filtro-estado").value;
    const [filtradas, pendientes] = await Promise.all([
      api(`/api/solicitudes${estado ? `?estado=${estado}` : ""}`),
      api("/api/solicitudes?estado=PENDIENTE"),
    ]);
    const lista = $("[data-testid=lista-solicitudes]");
    lista.innerHTML = "";
    if (!filtradas.ok) return;
    if (pendientes.ok) {
      $("[data-testid=contador-recibidas]").textContent = pendientes.datos.recibidas.length ? `(${pendientes.datos.recibidas.length})` : "";
      $("[data-testid=contador-enviadas]").textContent = pendientes.datos.enviadas.length ? `(${pendientes.datos.enviadas.length})` : "";
    }
    const solicitudes = filtradas.datos[vista];
    if (!solicitudes.length) {
      lista.appendChild(itemVacio(vista === "recibidas" ? "No tienes solicitudes recibidas" : "No tienes solicitudes enviadas"));
      return;
    }
    solicitudes.forEach((s) => lista.appendChild(itemSolicitud(s)));
  }

  $$(".pestanas button").forEach((b) => b.addEventListener("click", () => {
    vista = b.dataset.vista;
    $$(".pestanas button").forEach((otro) => otro.setAttribute("aria-selected", String(otro === b)));
    cargar();
  }));
  $("#filtro-estado").addEventListener("change", cargar);

  $("#form-solicitud").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultar(mensaje);
    if (!$("#sol-contacto").value) {
      mostrarAlerta(mensaje, "Elige un contacto");
      return;
    }
    const botonSolicitar = $("#boton-solicitar");
    bloquear(botonSolicitar, true, "Enviando...");
    const resultado = await api("/api/solicitudes", {
      metodo: "POST",
      cuerpo: { contacto_id: Number($("#sol-contacto").value), monto: $("#sol-monto").value.trim(), motivo: $("#sol-motivo").value },
    });
    bloquear(botonSolicitar, false);
    if (!resultado.ok) {
      mostrarAlerta(mensaje, mensajeDeError(resultado));
      return;
    }
    evento.target.reset();
    mostrarAlerta(mensaje, `Solicitud enviada. Vence el ${fechaLegible(resultado.datos.vence_en)}`, "exito");
    vista = "enviadas";
    $$(".pestanas button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.vista === vista)));
    cargar();
  });
  cargar();
};

/* ---------- Límites y alertas ---------- */

const NOMBRES_TIPO_ALERTA = {
  TRANSFERENCIAS: "Transferencias",
  RECARGAS: "Recargas",
  PAGOS: "Pagos de servicios",
  TODAS: "Todos mis gastos",
};

paginas.limites = async () => {
  const mensaje = $("#limites-mensaje");

  async function cargar() {
    const resultado = await api("/api/limites");
    if (!resultado.ok) return;
    const l = resultado.datos;
    $("[data-testid=limite-operacion]").textContent = soles(l.limite_por_operacion);
    $("[data-testid=limite-diario]").textContent = soles(l.limite_diario);
    $("[data-testid=limite-usado]").textContent = soles(l.usado_hoy);
    $("[data-testid=limite-disponible]").textContent = soles(l.disponible_hoy);
    const porcentaje = Math.min(100, (Number(l.usado_hoy) / Number(l.limite_diario)) * 100 || 0);
    $("[data-testid=barra-uso] > div").style.width = `${porcentaje}%`;
    const pendiente = $("[data-testid=limite-pendiente]");
    if (l.limite_pendiente) {
      pendiente.textContent = `Aumento a ${soles(l.limite_pendiente)} programado desde ${fechaLegible(l.pendiente_desde)}`;
      pendiente.hidden = false;
    } else {
      pendiente.hidden = true;
    }
  }

  $("#form-limite").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultar(mensaje);
    const botonGuardar = $("#boton-guardar-limite");
    bloquear(botonGuardar, true, "Guardando...");
    const resultado = await api("/api/limites", { metodo: "PUT", cuerpo: { limite_diario: $("#nuevo-limite").value } });
    bloquear(botonGuardar, false);
    if (!resultado.ok) {
      mostrarAlerta(mensaje, mensajeDeError(resultado));
      return;
    }
    const texto = resultado.datos.aplicacion === "PROGRAMADA"
      ? `El aumento estará vigente desde ${fechaLegible(resultado.datos.pendiente_desde)}`
      : "Tu límite diario fue actualizado";
    mostrarAlerta(mensaje, texto, "exito");
    cargar();
    cargarAlertas();
  });

  /* Alertas */
  const errorAlerta = $("#alerta-error");

  async function editarAlerta(alerta) {
    const editada = await dialogoFormulario({
      titulo: `Editar alerta de ${NOMBRES_TIPO_ALERTA[alerta.tipo].toLowerCase()}`,
      campos: [{ id: "editar-umbral", etiqueta: "Umbral (S/)", tipo: "number", step: 10, valor: Number(alerta.umbral),
                 ayuda: "Entre S/ 10 y S/ 2,000, en múltiplos de S/ 10" }],
      alEnviar: (v) => api(`/api/limites/alertas/${alerta.id}`, { metodo: "PUT", cuerpo: { umbral: v["editar-umbral"] } }),
    });
    if (editada) {
      toast("Alerta actualizada");
      cargarAlertas();
    }
  }

  async function cambiarEstado(alerta) {
    const nuevo = alerta.estado === "ACTIVA" ? "PAUSADA" : "ACTIVA";
    const resultado = await api(`/api/limites/alertas/${alerta.id}`, { metodo: "PUT", cuerpo: { estado: nuevo } });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    toast(nuevo === "ACTIVA" ? "Alerta reanudada" : "Alerta pausada");
    cargarAlertas();
  }

  async function eliminarAlerta(alerta) {
    if (!await confirmar("¿Eliminar alerta?", `Dejarás de recibir avisos de ${NOMBRES_TIPO_ALERTA[alerta.tipo].toLowerCase()} desde ${soles(alerta.umbral)}.`, "Eliminar", true)) return;
    const resultado = await api(`/api/limites/alertas/${alerta.id}`, { metodo: "DELETE" });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    toast("Alerta eliminada");
    cargarAlertas();
  }

  async function cargarAlertas() {
    const resultado = await api("/api/limites/alertas");
    const lista = $("[data-testid=lista-alertas]");
    lista.innerHTML = "";
    if (!resultado.ok) return;
    $("[data-testid=contador-alertas]").textContent = `${resultado.datos.length} de 5`;
    if (!resultado.datos.length) lista.appendChild(itemVacio("No tienes alertas de consumo"));
    resultado.datos.forEach((a) => {
      const activa = a.estado === "ACTIVA";
      const porcentaje = Math.min(100, (Number(a.gasto_hoy) / Number(a.umbral)) * 100 || 0);
      lista.appendChild(h("li", { testid: "alerta", "data-id": a.id },
        h("div", { clase: "crece" },
          h("strong", { testid: "alerta-titulo", texto: `${NOMBRES_TIPO_ALERTA[a.tipo]} · desde ${soles(a.umbral)}` }), h("br"),
          h("small", { clase: "texto-suave", testid: "alerta-detalle",
                       texto: `Gasto de hoy: ${soles(a.gasto_hoy)} · Último aviso: ${a.ultima_notificacion ? fechaLegible(a.ultima_notificacion) : "nunca"}` }),
          h("div", { clase: "barra delgada", role: "presentation" }, h("div", { style: `width:${porcentaje}%` }))),
        h("div", { clase: "acciones" },
          h("span", { clase: `etiqueta-estado ${activa ? "exito" : "advertencia"}`, testid: "alerta-estado", texto: activa ? "Activa" : "Pausada" }),
          boton("Editar", "boton-editar-alerta", () => editarAlerta(a)),
          boton(activa ? "Pausar" : "Reanudar", activa ? "boton-pausar-alerta" : "boton-reanudar-alerta", () => cambiarEstado(a)),
          boton("Eliminar", "boton-eliminar-alerta", () => eliminarAlerta(a), "peligro"))));
    });
  }

  $("#form-alerta").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultar(errorAlerta);
    const resultado = await api("/api/limites/alertas", {
      metodo: "POST", cuerpo: { tipo: $("#alerta-tipo").value, umbral: $("#alerta-umbral").value },
    });
    if (!resultado.ok) {
      mostrarAlerta(errorAlerta, mensajeDeError(resultado));
      return;
    }
    $("#alerta-umbral").value = "";
    toast("Alerta creada");
    cargarAlertas();
  });

  cargar();
  cargarAlertas();
};

/* ---------- Seguridad: PIN, dispositivos y sesiones ---------- */

const NOMBRES_TIPO_DISPOSITIVO = { CELULAR: "Celular", TABLET: "Tablet", COMPUTADORA: "Computadora" };

paginas.seguridad = async () => {
  $("#form-pin").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const mensaje = $("#pin-mensaje");
    ocultar(mensaje);
    if ($("#pin-nuevo").value !== $("#pin-confirmacion").value) {
      mostrarAlerta(mensaje, "La confirmación no coincide con el nuevo PIN");
      return;
    }
    const botonPin = $("#boton-cambiar-pin");
    bloquear(botonPin, true, "Guardando...");
    const resultado = await api("/api/seguridad/pin", {
      metodo: "PUT", cuerpo: { pin_actual: $("#pin-actual").value, pin_nuevo: $("#pin-nuevo").value },
    });
    bloquear(botonPin, false);
    if (resultado.ok) {
      evento.target.reset();
      mostrarAlerta(mensaje, resultado.datos.mensaje, "exito");
      cargarSesiones();
    } else {
      mostrarAlerta(mensaje, mensajeDeError(resultado));
    }
  });

  /* Dispositivos */
  const errorDispositivo = $("#dispositivo-error");

  async function renombrar(dispositivo) {
    const editado = await dialogoFormulario({
      titulo: "Renombrar dispositivo",
      campos: [{ id: "nuevo-nombre", etiqueta: "Nombre", valor: dispositivo.nombre, ayuda: "Entre 3 y 30 caracteres" }],
      alEnviar: (v) => api(`/api/seguridad/dispositivos/${dispositivo.id}`, { metodo: "PUT", cuerpo: { nombre: v["nuevo-nombre"] } }),
    });
    if (editado) {
      if (dispositivoLocal.leer()?.id === dispositivo.id) dispositivoLocal.guardar(editado);
      toast("Dispositivo renombrado");
      cargarDispositivos();
    }
  }

  async function eliminar(dispositivo) {
    const texto = `Si vuelves a ingresar desde "${dispositivo.nombre}", te enviaremos una alerta de nuevo dispositivo.`;
    if (!await confirmar("¿Eliminar dispositivo?", texto, "Eliminar", true)) return;
    const resultado = await api(`/api/seguridad/dispositivos/${dispositivo.id}`, { metodo: "DELETE" });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    toast("Dispositivo eliminado");
    cargarDispositivos();
  }

  async function cargarDispositivos() {
    const resultado = await api("/api/seguridad/dispositivos");
    const lista = $("[data-testid=lista-dispositivos]");
    lista.innerHTML = "";
    if (!resultado.ok) return;
    $("[data-testid=contador-dispositivos]").textContent = `${resultado.datos.length} de 3`;
    const local = dispositivoLocal.leer();
    if (!resultado.datos.length) lista.appendChild(itemVacio("No tienes dispositivos de confianza"));
    resultado.datos.forEach((d) => {
      const esEste = local?.id === d.id;
      lista.appendChild(h("li", { testid: "dispositivo", "data-id": d.id },
        h("div", {},
          h("strong", { testid: "dispositivo-nombre", texto: d.nombre }), " ",
          esEste ? h("span", { clase: "etiqueta-estado info", testid: "dispositivo-actual", texto: "Este dispositivo" }) : null, h("br"),
          h("small", { clase: "texto-suave", testid: "dispositivo-detalle",
                       texto: `${NOMBRES_TIPO_DISPOSITIVO[d.tipo] || d.tipo} · Registrado el ${fechaLegible(d.registrado_en)} · Último ingreso: ${d.ultimo_ingreso ? fechaLegible(d.ultimo_ingreso) : "nunca"}` })),
        h("div", { clase: "acciones" },
          esEste ? null : boton("Usar en este navegador", "boton-usar-dispositivo", () => {
            dispositivoLocal.guardar(d);
            toast(`Este navegador ahora se identifica como "${d.nombre}"`);
            cargarDispositivos();
          }),
          boton("Renombrar", "boton-renombrar-dispositivo", () => renombrar(d)),
          boton("Eliminar", "boton-eliminar-dispositivo", () => eliminar(d), "peligro"))));
    });
  }

  $("#form-dispositivo").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    ocultar(errorDispositivo);
    const botonRegistrar = $("#boton-registrar-dispositivo");
    bloquear(botonRegistrar, true, "Registrando...");
    const resultado = await api("/api/seguridad/dispositivos", {
      metodo: "POST", cuerpo: { nombre: $("#disp-nombre").value, tipo: $("#disp-tipo").value, pin: $("#disp-pin").value },
    });
    bloquear(botonRegistrar, false);
    if (!resultado.ok) {
      mostrarAlerta(errorDispositivo, mensajeDeError(resultado));
      return;
    }
    if ($("#disp-este").checked) dispositivoLocal.guardar(resultado.datos);
    evento.target.reset();
    $("#disp-este").checked = true;
    toast(`Dispositivo "${resultado.datos.nombre}" registrado`);
    cargarDispositivos();
  });

  /* Sesiones */
  async function cerrarSesion(sesionListada) {
    const texto = sesionListada.actual
      ? "Es la sesión que estás usando: tendrás que volver a ingresar."
      : `La sesión iniciada el ${fechaLegible(sesionListada.iniciada_en)} dejará de funcionar de inmediato.`;
    if (!await confirmar("¿Cerrar sesión?", texto, "Cerrar sesión", true)) return;
    const resultado = await api(`/api/seguridad/sesiones/${sesionListada.id}`, { metodo: "DELETE" });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    toast("Sesión cerrada");
    cargarSesiones();
  }

  async function cargarSesiones() {
    const resultado = await api("/api/seguridad/sesiones");
    const lista = $("[data-testid=lista-sesiones]");
    lista.innerHTML = "";
    if (!resultado.ok) return;
    resultado.datos.forEach((s) => {
      const dispositivo = s.dispositivo ? (s.dispositivo.nombre || "Dispositivo no registrado") : "Sin dispositivo indicado";
      lista.appendChild(h("li", { testid: "sesion", "data-id": s.id },
        h("div", {},
          h("strong", { testid: "sesion-dispositivo", texto: dispositivo }), " ",
          s.actual ? h("span", { clase: "etiqueta-estado info", testid: "sesion-actual", texto: "Sesión actual" }) : null, h("br"),
          h("small", { clase: "texto-suave", testid: "sesion-detalle",
                       texto: `Inició ${fechaLegible(s.iniciada_en)} · Vence ${fechaLegible(s.expira_en)}` })),
        boton("Cerrar", "boton-cerrar-sesion-especifica", () => cerrarSesion(s), "peligro")));
    });
    $("#boton-cerrar-otras").disabled = resultado.datos.filter((s) => !s.actual).length === 0;
  }

  $("#boton-cerrar-otras").addEventListener("click", async () => {
    if (!await confirmar("¿Cerrar las demás sesiones?", "Todas tus sesiones, excepto esta, dejarán de funcionar de inmediato.", "Cerrar sesiones", true)) return;
    const resultado = await api("/api/seguridad/sesiones", { metodo: "DELETE" });
    if (!resultado.ok) {
      toast(mensajeDeError(resultado), "error");
      return;
    }
    toast(`Se cerraron ${resultado.datos.sesiones_cerradas} sesiones`);
    cargarSesiones();
  });

  cargarDispositivos();
  cargarSesiones();
};

/* ---------- Arranque ---------- */

document.addEventListener("DOMContentLoaded", () => {
  const pagina = document.body.dataset.pagina;
  const publicas = ["login", "registro", "desbloqueo"];
  if (!publicas.includes(pagina)) {
    if (!requiereSesion()) return;
    montarMenu(pagina);
  }
  paginas[pagina]?.();
});

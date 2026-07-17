export type LinkType = "push" | "view" | "room" | "unknown";

export interface ValidationResult {
  isValid: boolean;
  type?: LinkType;
  message: string;
  sanitizedUrl?: string;
  isError: boolean;
}

export function validateVdoNinjaLink(inputUrl: string): ValidationResult {
  // 1. Remove spaces at start and end
  const trimmed = inputUrl.trim();

  // 2. Detect incomplete or empty
  if (!trimmed) {
    return {
      isValid: false,
      isError: true,
      message: "El enlace está vacío. Por favor, pega un enlace válido."
    };
  }

  // 3. Prevent HTML/JS (Basic sanity check)
  if (/<[a-z][\s\S]*>/i.test(trimmed) || /javascript:/i.test(trimmed)) {
    return {
      isValid: false,
      isError: true,
      message: "El enlace contiene caracteres no permitidos."
    };
  }

  let parsedUrl: URL;
  try {
    // Attempt to parse the URL
    parsedUrl = new URL(trimmed);
  } catch {
    return {
      isValid: false,
      isError: true,
      message: "No pudimos reconocer este enlace. Copia nuevamente el enlace proporcionado por VDO.Ninja."
    };
  }

  // 4. Block non-HTTPS
  if (parsedUrl.protocol !== "https:") {
    return {
      isValid: false,
      isError: true,
      message: "El enlace debe ser seguro (HTTPS)."
    };
  }

  // 5. Block non-vdo.ninja domains
  const validDomains = ["vdo.ninja", "www.vdo.ninja"];
  if (!validDomains.includes(parsedUrl.hostname.toLowerCase())) {
    return {
      isValid: false,
      isError: true,
      message: "Solo se permiten enlaces de VDO.Ninja."
    };
  }

  // 6. Classify link type
  const searchParams = parsedUrl.search;
  let linkType: LinkType = "unknown";
  
  if (searchParams.includes("push=")) {
    linkType = "push";
  } else if (searchParams.includes("view=")) {
    linkType = "view";
  } else if (searchParams.includes("room=")) {
    linkType = "room";
  }

  let message = "El video está disponible y puede utilizarse en tu transmisión.";
  let isError = false;

  if (linkType === "push") {
    message = "Este enlace se utiliza para transmitir desde el teléfono. Abre el enlace en tu teléfono y utiliza el enlace de visualización correspondiente en StreamML.";
    isError = true;
    return { isValid: false, type: linkType, message, isError };
  } else if (linkType === "room") {
    message = "Has introducido un enlace de sala. Usaremos este enlace, pero asegúrate de que haya alguien transmitiendo en ella.";
  } else if (linkType === "unknown") {
    message = "El enlace parece válido, pero no pudimos determinar su tipo exacto.";
  }

  return {
    isValid: true,
    type: linkType,
    message,
    sanitizedUrl: parsedUrl.toString(),
    isError: false
  };
}

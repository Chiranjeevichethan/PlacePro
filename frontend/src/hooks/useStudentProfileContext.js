/**
 * The shared student profile context VALUE (no components here, so the
 * react-refresh rule stays happy). The provider lives in
 * StudentProfileProvider.jsx; pages read the value through this hook.
 */
import { createContext, useContext } from "react";

export const StudentProfileContext = createContext(null);

export function useStudentProfileContext() {
  const context = useContext(StudentProfileContext);

  if (!context) {
    throw new Error(
      "useStudentProfileContext must be used inside StudentProfileProvider"
    );
  }

  return context;
}

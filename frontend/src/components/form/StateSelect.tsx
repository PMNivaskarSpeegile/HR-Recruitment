import { Combobox } from "@/components/ui/combobox";
import { INDIAN_STATES } from "@/lib/geo";

/**
 * Reusable State / Union Territory dropdown — searchable, keyboard-navigable,
 * alphabetical. Stores the selected value as a string. Options come from the
 * shared list in lib/geo.
 */
export function StateSelect({
  value,
  onChange,
  id,
  invalid,
}: {
  value: string;
  onChange: (v: string) => void;
  id?: string;
  invalid?: boolean;
}) {
  return (
    <Combobox
      id={id}
      value={value ?? ""}
      onChange={onChange}
      options={INDIAN_STATES}
      placeholder="Select State / Union Territory"
      searchPlaceholder="Search state / UT…"
      invalid={invalid}
    />
  );
}

package tn.isima.energy.job2;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.Objects;

import org.apache.hadoop.io.WritableComparable;

/**
 * Cle de regroupement MR2 : (foyer, mois, groupe tarifaire).
 * Exemple : ("MAC000002", "2013-03", "Std").
 *
 * WritableComparable = serialisation Hadoop + ordre naturel.
 * Regle d'or : write() et readFields() lisent/ecrivent dans le MEME ordre.
 */
public class HouseholdMonthKey implements WritableComparable<HouseholdMonthKey> {

    // "" par defaut : writeUTF refuse null et planterait la serialisation.
    private String householdId = "";
    private String yearMonth   = "";
    private String tariffGroup = "";

    /** Constructeur vide obligatoire : Hadoop cree l'objet puis appelle readFields(). */
    public HouseholdMonthKey() {
    }

    public HouseholdMonthKey(String householdId, String yearMonth, String tariffGroup) {
        this.householdId = orEmpty(householdId);
        this.yearMonth   = orEmpty(yearMonth);
        this.tariffGroup = orEmpty(tariffGroup);
    }

    // ---------- accesseurs ----------

    public String getHouseholdId() { return householdId; }
    public String getYearMonth()   { return yearMonth; }
    public String getTariffGroup() { return tariffGroup; }

    // Les setters normalisent null -> "" pour proteger writeUTF.
    public void setHouseholdId(String v) { this.householdId = orEmpty(v); }
    public void setYearMonth(String v)   { this.yearMonth   = orEmpty(v); }
    public void setTariffGroup(String v) { this.tariffGroup = orEmpty(v); }

    // ---------- serialisation Hadoop ----------

    @Override
    public void write(DataOutput out) throws IOException {
        out.writeUTF(householdId);
        out.writeUTF(yearMonth);
        out.writeUTF(tariffGroup);
    }

    @Override
    public void readFields(DataInput in) throws IOException {
        householdId = in.readUTF();
        yearMonth   = in.readUTF();
        tariffGroup = in.readUTF();
    }

    // ---------- ordre naturel : foyer, puis mois, puis tarif ----------

    @Override
    public int compareTo(HouseholdMonthKey other) {
        int c = householdId.compareTo(other.householdId);
        if (c != 0) return c;

        c = yearMonth.compareTo(other.yearMonth);
        if (c != 0) return c;

        return tariffGroup.compareTo(other.tariffGroup);
    }

    /**
     * equals coherent avec compareTo :
     * compareTo == 0  <=>  les trois chaines sont egales  <=>  equals == true.
     */
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof HouseholdMonthKey)) return false;

        HouseholdMonthKey other = (HouseholdMonthKey) o;
        return householdId.equals(other.householdId)
                && yearMonth.equals(other.yearMonth)
                && tariffGroup.equals(other.tariffGroup);
    }

    @Override
    public int hashCode() {
        return Objects.hash(householdId, yearMonth, tariffGroup);
    }

    /** Format lisible pour les logs : MAC000002|2013-03|Std */
    @Override
    public String toString() {
        return householdId + "|" + yearMonth + "|" + tariffGroup;
    }

    /** Evite les null dans les champs texte. */
    private static String orEmpty(String s) {
        return s == null ? "" : s;
    }
}
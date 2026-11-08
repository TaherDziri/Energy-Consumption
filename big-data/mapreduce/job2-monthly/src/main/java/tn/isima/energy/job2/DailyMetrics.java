package tn.isima.energy.job2;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.Locale;
import java.util.Objects;

import org.apache.hadoop.io.Writable;

/**
 * Seau additionnable : une ligne journaliere MR1, ou plusieurs fusionnees
 * en un mois par merge().
 *
 * merge() est associative : SOMME pour les champs additifs, MAX pour le pic.
 * Unites : totalKwh et peakKwhHh en kWh/30 min, costGbp en GBP.
 */
public class DailyMetrics implements Writable {

    private double totalKwh;      // somme des creneaux observes (kWh)
    private double peakKwhHh;     // max d'un creneau de 30 min (kWh)
    private double costGbp;       // 0.0 tant que pricedSlots == 0 ; NULL decide en sortie
    private long observedSlots;   // n_valid_slots de MR1
    private long pricedSlots;     // creneaux trouves dans le calendrier tarifaire
    private long missingSlots;    // n_missing_slots de MR1
    private int validDays;        // jours avec au moins un creneau valide

    /**
     * Constructeur vide obligatoire pour Hadoop.
     * costGbp reste 0.0 : un NaN contaminerait toutes les sommes suivantes.
     * Le cout NULL est une decision d'affichage (pricedSlots == 0), pas une valeur interne.
     */
    public DailyMetrics() {
    }

    // ---------- accesseurs ----------

    public double getTotalKwh()    { return totalKwh; }
    public double getPeakKwhHh()   { return peakKwhHh; }
    public double getCostGbp()     { return costGbp; }
    public long getObservedSlots() { return observedSlots; }
    public long getPricedSlots()   { return pricedSlots; }
    public long getMissingSlots()  { return missingSlots; }
    public int getValidDays()      { return validDays; }

    public void setTotalKwh(double v)    { this.totalKwh = v; }
    public void setPeakKwhHh(double v)   { this.peakKwhHh = v; }
    public void setCostGbp(double v)     { this.costGbp = v; }
    public void setObservedSlots(long v) { this.observedSlots = v; }
    public void setPricedSlots(long v)   { this.pricedSlots = v; }
    public void setMissingSlots(long v)  { this.missingSlots = v; }
    public void setValidDays(int v)      { this.validDays = v; }

    // ---------- serialisation Hadoop ----------
    // Ordre : 3 doubles, 3 longs, 1 int. Le meme ordre dans readFields.

    @Override
    public void write(DataOutput out) throws IOException {
        out.writeDouble(totalKwh);
        out.writeDouble(peakKwhHh);
        out.writeDouble(costGbp);
        out.writeLong(observedSlots);
        out.writeLong(pricedSlots);
        out.writeLong(missingSlots);
        out.writeInt(validDays);
    }

    @Override
    public void readFields(DataInput in) throws IOException {
        totalKwh      = in.readDouble();
        peakKwhHh     = in.readDouble();
        costGbp       = in.readDouble();
        observedSlots = in.readLong();
        pricedSlots   = in.readLong();
        missingSlots  = in.readLong();
        validDays     = in.readInt();
    }

    // ---------- fusion ----------

    /**
     * Absorbe une ligne journaliere (ou un seau partiel) dans celui-ci.
     * SOMME pour tout le reste, MAX pour le pic. Jamais de moyenne ni de ratio.
     * Utilise par le Reducer :
     *
     *   DailyMetrics month = new DailyMetrics();
     *   for (DailyMetrics d : values) month.merge(d);
     */
    public void merge(DailyMetrics other) {
        if (other == null) return;

        this.totalKwh      += other.totalKwh;
        this.costGbp       += other.costGbp;
        this.observedSlots += other.observedSlots;
        this.pricedSlots   += other.pricedSlots;
        this.missingSlots  += other.missingSlots;
        this.validDays     += other.validDays;

        // MAX : un max de max reste un max.
        if (other.peakKwhHh > this.peakKwhHh) {
            this.peakKwhHh = other.peakKwhHh;
        }
    }

    // ---------- egalite et affichage ----------

    // Double.compare evite le piege de == sur les double (NaN, -0.0).
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof DailyMetrics)) return false;

        DailyMetrics other = (DailyMetrics) o;
        return Double.compare(totalKwh, other.totalKwh) == 0
                && Double.compare(peakKwhHh, other.peakKwhHh) == 0
                && Double.compare(costGbp, other.costGbp) == 0
                && observedSlots == other.observedSlots
                && pricedSlots == other.pricedSlots
                && missingSlots == other.missingSlots
                && validDays == other.validDays;
    }

    @Override
    public int hashCode() {
        return Objects.hash(totalKwh, peakKwhHh, costGbp,
                observedSlots, pricedSlots, missingSlots, validDays);
    }

    /** Format lisible pour les logs. */
    @Override
    public String toString() {
        return String.format(Locale.ROOT,
                "kwh=%.3f peak=%.3f cost=%.6f obs=%d priced=%d missing=%d days=%d",
                totalKwh, peakKwhHh, costGbp,
                observedSlots, pricedSlots, missingSlots, validDays);
    }
}
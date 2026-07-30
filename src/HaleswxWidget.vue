<!--
# Copyright 2026 OpenC3, Inc.
# All Rights Reserved.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE.md for more details.
#
# This file may also be used under the terms of a commercial license
# if purchased from OpenC3, Inc.
#
# HALESWX <TARGET> <PACKET> <WIDTH (optional)>
#
# Displays a HaleSWx CssiSpaceWeather response packet: current conditions as
# stat tiles, F10.7 solar radio flux as a line chart and the daily average Kp
# index as a column chart. Chrome is Vuetify, charts are uPlot (the same chart
# library the stock COSMOS graph widgets use).
-->

<template>
  <v-card :width="width" class="swx" variant="flat">
    <v-card-item>
      <template #prepend>
        <img :src="logo" class="swx-logo" alt="HaleSWx" />
      </template>
      <v-card-title class="text-subtitle-1">Space Weather</v-card-title>
      <v-card-subtitle class="text-caption">
        {{ parameters[0] }} {{ parameters[1] }}
        <span v-if="updated"> &middot; updated {{ updated }}</span>
      </v-card-subtitle>
      <template #append>
        <v-btn-toggle v-model="view" density="compact" divided mandatory>
          <v-btn size="small" value="charts">Charts</v-btn>
          <v-btn size="small" value="table">Table</v-btn>
        </v-btn-toggle>
        <!-- Values already refresh on their own with the screen's polling
             period; this redraws the charts from whatever is in the CVT right
             now, which is also how you recover a plot that was sized while its
             tab was hidden. -->
        <v-btn
          class="ml-2"
          density="comfortable"
          icon="mdi-refresh"
          size="small"
          title="Redraw from the current values"
          variant="text"
          @click="build"
        />
      </template>
    </v-card-item>

    <v-card-text v-if="usage" class="text-medium-emphasis">
      {{ usage }}
    </v-card-text>
    <v-card-text v-else-if="!hasData" class="text-medium-emphasis">
      Waiting for {{ parameters[1] }}&hellip;
    </v-card-text>

    <v-card-text v-else>
      <!-- Current conditions. Single headline numbers, so stat tiles rather
           than a chart. Kp and F10.7 each carry a band chip so the two can be
           read against each other without knowing either scale; the chips take
           their color from the same ramp as the charts, and always ship with an
           icon and a label, never hue alone. -->
      <v-row dense>
        <v-col v-for="tile in tiles" :key="tile.label" cols="3">
          <div class="text-caption text-medium-emphasis">{{ tile.label }}</div>
          <div class="text-h5">
            {{ tile.value
            }}<span class="text-caption text-medium-emphasis">{{
              tile.unit
            }}</span>
          </div>
          <v-chip
            v-if="tile.status"
            :color="tile.status.color"
            :prepend-icon="tile.status.icon"
            :style="{ color: tile.status.text }"
            size="x-small"
            variant="flat"
          >
            {{ tile.status.label }}
          </v-chip>
        </v-col>
      </v-row>

      <template v-if="view === 'charts'">
        <v-divider class="my-3" />
        <!-- uPlot supplies the legend with live values plus the crosshair, so
             every plotted value is readable on hover and on the Table view -->
        <div ref="fluxPlot" />
        <div ref="kpPlot" class="mt-2" />
        <div class="text-caption text-medium-emphasis mt-1">
          Shaded region is predicted. Kp bars are daily averages; the marked
          lines are the NOAA G1 and G3 storm thresholds.
        </div>
      </template>

      <v-data-table
        v-else
        :headers="headers"
        :items="days"
        :items-per-page="-1"
        class="swx-table text-body-2 mt-2"
        density="compact"
        fixed-header
        hide-default-footer
      >
        <!-- Slots keep the raw numbers sortable while displaying them at a
             fixed precision -->
        <template #item.predicted="{ item }">
          {{ item.predicted ? 'Predicted' : 'Observed' }}
        </template>
        <template #item.kp="{ item }">{{ fmt(item.kp, 2) }}</template>
        <template #item.ap="{ item }">{{ fmt(item.ap, 0) }}</template>
        <template #item.f107="{ item }">{{ fmt(item.f107, 1) }}</template>
        <template #item.isn="{ item }">{{ fmt(item.isn, 0) }}</template>
      </v-data-table>
    </v-card-text>
  </v-card>
</template>

<script>
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
// Inlined as a data URI by assetsInlineLimit in vite.config.js
import logo from './hale_logo.svg'

// Brand palette. Everything plotted is one sequential ramp: low values sit at
// the pale end, high values at the deep end, so a taller mark is also a hotter
// one and magnitude is encoded twice.
const RAMP = ['#FFF36D', '#FF8D21', '#FB191A', '#4B0000']
// Brand neutrals. INK is the surface, PAPER is the ink on top of it; chrome is
// PAPER stepped down in alpha so nothing competes with the ramp.
const INK = '#110202'
const PAPER = '#E7E8E3'
const GRID = rgba(PAPER, 0.12)
const MUTED = rgba(PAPER, 0.6)
const FORECAST_WASH = rgba(PAPER, 0.05)
const PANEL = rgba(PAPER, 0.06)
// A CSS border cannot hold a canvas gradient, so the legend markers and any
// pre-layout draw fall back to the middle of the ramp
const MARK = RAMP[1]

// #RRGGBB plus an alpha, for the washes under the ramp
function rgba(hex, alpha) {
  const n = Number.parseInt(hex.slice(1), 16)
  return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`
}
// Storm state reads off the same ramp, so a G3 chip is the same red as a tall
// bar. Always beside an icon and a label, never hue alone. The deep end of the
// ramp is reserved for the plots -- a chip has to carry INK text, and #4B0000
// is too dark a bed for that.
const LEVELS = [
  { max: 5, label: 'Below G1', color: RAMP[0], text: INK, icon: 'mdi-check-circle' },
  { max: 7, label: 'G1-G2 storm', color: RAMP[1], text: INK, icon: 'mdi-alert' },
  { max: Infinity, label: 'G3+ storm', color: RAMP[2], text: INK, icon: 'mdi-flash' },
]
// F10.7 has no storm scale of its own, so these are the conventional solar
// activity bands. Same ramp as the Kp chips and the charts, which is what lets
// the two tiles be read against each other at a glance. The top band is the
// deep end of the ramp and takes PAPER text, the rest are dark on light.
const F107_LEVELS = [
  { max: 100, label: 'Low flux', color: RAMP[0], text: INK, icon: 'mdi-weather-sunny' },
  { max: 150, label: 'Moderate flux', color: RAMP[1], text: INK, icon: 'mdi-white-balance-sunny' },
  { max: 200, label: 'High flux', color: RAMP[2], text: INK, icon: 'mdi-flare' },
  { max: Infinity, label: 'Very high flux', color: RAMP[3], text: PAPER, icon: 'mdi-flare' },
]
const G1_KP = 5
const G3_KP = 7
// Kp runs 0-9 by definition; F10.7 axis snaps to whole steps of this size
const KP_MAX = 9
const F107_STEP = 20
// Value domains the color ramp is anchored to. Kp is its own full scale. F10.7
// has no ceiling, so the ramp spans the solar-minimum floor to a strongly
// active sun; anything above simply sits at the deep end.
const KP_RAMP = [0, KP_MAX]
const F107_RAMP = [65, 300]
// Alpha for the wash under the observed flux line
const WASH = 0.18
// Kp bar width in px, fixed so it doesn't vary with the packet's day count
const BAR_PX = 9
const SERIES_ITEMS = [
  'DATES',
  'KP_AVGS',
  'AP_AVGS',
  'F107_OBSS',
  'ISNS',
]
const FONT = "11px system-ui, -apple-system, 'Segoe UI', sans-serif"

export default {
  props: {
    // TARGET, PACKET and optional WIDTH from the screen definition
    parameters: {
      type: Array,
      default: () => [],
    },
    // SETTING lines following the widget, e.g. ['WIDTH', '900']
    settings: {
      type: Array,
      default: () => [],
    },
    // Values the screen polls for us, keyed TGT__PKT__ITEM__TYPE and holding
    // [value, limitsState, counter]
    screenValues: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['addItem', 'deleteItem'],
  data() {
    return {
      logo,
      width: 760,
      view: 'charts',
      usage: null,
      plots: [],
      headers: [
        { title: 'Date', key: 'date' },
        { title: 'Type', key: 'predicted' },
        { title: 'Kp', key: 'kp', align: 'end' },
        { title: 'ap (nT)', key: 'ap', align: 'end' },
        { title: 'F10.7 (sfu)', key: 'f107', align: 'end' },
        { title: 'Sunspots', key: 'isn', align: 'end' },
      ],
    }
  },
  computed: {
    // Every item the screen polls for us
    valueIds() {
      if (!this.parameters[0] || !this.parameters[1]) {
        return []
      }
      return [
        'UPDATED',
        ...SERIES_ITEMS.map((name) => `OBSERVED_${name}`),
        ...SERIES_ITEMS.map((name) => `PREDICTED_${name}`),
      ].map(
        (item) =>
          `${this.parameters[0]}__${this.parameters[1]}__${item}__CONVERTED`,
      )
    },
    updated() {
      return this.itemValue('UPDATED')
    },
    // One flat timeline: observed days followed by predicted days
    days() {
      const out = []
      for (const [prefix, predicted] of [
        ['OBSERVED', false],
        ['PREDICTED', true],
      ]) {
        const [dates, kp, ap, f107, isn] = SERIES_ITEMS.map(
          (name) => this.itemValue(`${prefix}_${name}`) || [],
        )
        dates.forEach((date, i) => {
          out.push({
            date: String(date),
            time: Date.parse(`${date}T00:00:00Z`) / 1000,
            predicted,
            kp: this.num(kp[i]),
            ap: this.num(ap[i]),
            f107: this.num(f107[i]),
            isn: this.num(isn[i]),
          })
        })
      }
      return out.filter((day) => Number.isFinite(day.time))
    },
    hasData() {
      return this.days.length > 1
    },
    latest() {
      const observed = this.days.filter((day) => !day.predicted)
      return observed[observed.length - 1] || {}
    },
    tiles() {
      return [
        {
          label: 'Average Kp',
          value: this.fmt(this.latest.kp, 2),
          unit: '',
          status: this.level(this.latest.kp),
        },
        {
          label: 'Average ap',
          value: this.fmt(this.latest.ap, 0),
          unit: ' nT',
        },
        {
          label: 'F10.7 observed',
          value: this.fmt(this.latest.f107, 1),
          unit: ' sfu',
          status: this.level(this.latest.f107, F107_LEVELS),
        },
        {
          label: 'Sunspot number',
          value: this.fmt(this.latest.isn, 0),
          unit: '',
        },
      ]
    },
    fluxData() {
      // The predicted line repeats the last observed point so the forecast
      // reads as continuous; the dash pattern is what marks it as forecast
      const lastObserved = this.days.filter((day) => !day.predicted).length - 1
      return [
        this.days.map((day) => day.time),
        this.days.map((day) => (day.predicted ? null : day.f107)),
        this.days.map((day, i) =>
          day.predicted || i === lastObserved ? day.f107 : null,
        ),
      ]
    },
    kpData() {
      return [this.days.map((day) => day.time), this.days.map((day) => day.kp)]
    },
    // Where the forecast begins. Each chart gets the boundary that lines up
    // with its own marks, so the shading never starts in a different place
    // than the thing it is shading:
    //   line -- the last observed point, which is exactly where the dashed
    //           predicted segment starts
    //   bars -- half a day later, the left edge of the first predicted bar,
    //           since bars are centered on their day
    forecastStart() {
      const observed = this.days.filter((day) => !day.predicted)
      const lastObserved = observed[observed.length - 1]
      const firstPredicted = this.days.find((day) => day.predicted)
      if (!lastObserved || !firstPredicted) {
        return null
      }
      return {
        line: lastObserved.time,
        bars: (lastObserved.time + firstPredicted.time) / 2,
      }
    },
  },
  watch: {
    days() {
      this.redraw()
    },
    view() {
      // The plot divs only exist in the charts view
      this.$nextTick(() => this.build())
    },
  },
  created() {
    if (!this.parameters[0] || !this.parameters[1]) {
      this.usage = 'Usage: HALESWX <TARGET> <PACKET> <WIDTH (optional)>'
      return
    }
    const setting = this.settings.find((s) => s[0] === 'WIDTH')
    const width = Number.parseInt(setting ? setting[1] : this.parameters[2])
    if (Number.isFinite(width)) {
      this.width = width
    }
    for (const valueId of this.valueIds) {
      this.$emit('addItem', valueId)
    }
  },
  mounted() {
    this.build()
  },
  unmounted() {
    this.destroyPlots()
    for (const valueId of this.valueIds) {
      this.$emit('deleteItem', valueId)
    }
  },
  methods: {
    itemValue(item) {
      const key = `${this.parameters[0]}__${this.parameters[1]}__${item}__CONVERTED`
      const entry = this.screenValues && this.screenValues[key]
      return entry ? entry[0] : null
    },
    num(value) {
      const parsed = Number.parseFloat(value)
      return Number.isFinite(parsed) ? parsed : null
    },
    fmt(value, digits) {
      return value === null || value === undefined
        ? '--'
        : Number(value).toFixed(digits)
    },
    level(value, levels = LEVELS) {
      return value === null || value === undefined
        ? null
        : levels.find((level) => value < level.max)
    },
    destroyPlots() {
      for (const plot of this.plots) {
        plot.destroy()
      }
      this.plots = []
    },
    redraw() {
      if (!this.plots.length) {
        this.build()
        return
      }
      this.plots[0].setData(this.fluxData)
      this.plots[1].setData(this.kpData)
    },
    // (Re)creates both charts from the current item values
    build() {
      this.destroyPlots()
      if (!this.hasData || this.view !== 'charts' || !this.$refs.fluxPlot) {
        return
      }
      const fluxOpts = {
        ...this.baseOpts('F10.7 Solar Radio Flux (sfu)'),
        series: [
          { label: 'Date' },
          {
            label: 'Observed',
            stroke: (u) => this.rampGradient(u, F107_RAMP),
            fill: (u) => this.rampGradient(u, F107_RAMP, WASH),
            width: 2,
            points: { show: false },
          },
          {
            label: 'Predicted',
            stroke: (u) => this.rampGradient(u, F107_RAMP),
            width: 2,
            dash: [5, 4],
            points: { show: false },
          },
        ],
        // F10.7 has no fixed ceiling, so snap the axis out to whole 20 sfu
        // steps. Nowcast revises the recent days slightly, and without this
        // those small differences move the axis and make the same week look
        // different between the two packets.
        scales: {
          y: {
            range: (u, min, max) => [
              Math.floor(min / F107_STEP) * F107_STEP,
              Math.ceil(max / F107_STEP) * F107_STEP,
            ],
          },
        },
        hooks: {
          drawClear: [this.drawPanel],
          draw: [(u) => this.drawForecastRegion(u, 'line')],
        },
      }
      const kpOpts = {
        ...this.baseOpts('Daily Average Kp Index'),
        series: [
          { label: 'Date' },
          {
            label: 'Avg Kp',
            stroke: (u) => this.rampGradient(u, KP_RAMP),
            fill: (u) => this.rampGradient(u, KP_RAMP),
            // A fixed pixel width (min and max both BAR_PX) so the bars look
            // the same no matter how many days the packet holds; a fractional
            // width would render forecast and nowcast bars differently
            paths: uPlot.paths.bars({ size: [1, BAR_PX, BAR_PX], radius: 0.2 }),
            points: { show: false },
          },
        ],
        // Kp is defined on a fixed 0-9 scale, so pin the axis there instead
        // of autoscaling. Forecast and nowcast then plot on identical axes
        // and are directly comparable, and the G1/G3 lines never move.
        scales: { y: { range: () => [0, KP_MAX] } },
        hooks: {
          drawClear: [this.drawPanel],
          draw: [(u) => this.drawForecastRegion(u, 'bars'), this.drawKpThresholds],
        },
      }
      this.plots = [
        new uPlot(fluxOpts, this.fluxData, this.$refs.fluxPlot),
        new uPlot(kpOpts, this.kpData, this.$refs.kpPlot),
      ]
    },
    baseOpts(title) {
      const axis = {
        stroke: MUTED,
        font: FONT,
        ticks: { stroke: GRID, width: 1 },
        grid: { stroke: GRID, width: 1 },
      }
      return {
        title,
        width: this.width - 40,
        height: 190,
        cursor: { y: false },
        legend: {
          live: true,
          markers: { stroke: () => MARK, fill: () => 'transparent' },
        },
        axes: [axis, { ...axis, size: 44 }],
      }
    },
    // The brand ramp painted up the plot area: pale at the low end of the
    // domain, deep at the high end, so a mark's color is a second reading of
    // its own height.
    //
    // The ramp is anchored to fixed values, not to whatever the axis happens to
    // be showing. A quiet week and an active week are then directly comparable:
    // 80 sfu is the same yellow in both, instead of every packet stretching the
    // full ramp across its own range.
    rampGradient(u, domain, alpha) {
      // uPlot also resolves stroke/fill while building the legend, before the
      // plot area has been measured, so there is no gradient to hand back yet
      if (!Number.isFinite(u.bbox.top) || !Number.isFinite(u.bbox.height)) {
        return alpha === undefined ? MARK : rgba(MARK, alpha)
      }
      const { top, height } = u.bbox
      const grad = u.ctx.createLinearGradient(0, top, 0, top + height)
      const [lo, hi] = domain
      // Canvas offsets run top-down, so walk the ramp from its high end. Values
      // outside the visible range clamp to the nearest edge, which is what puts
      // an off-the-chart flux at the deepest color rather than off the ramp.
      for (let i = RAMP.length - 1; i >= 0; i--) {
        const value = lo + ((hi - lo) * i) / (RAMP.length - 1)
        const pos = u.valToPos(value, 'y', true)
        const offset = Math.min(Math.max((pos - top) / height, 0), 1)
        const color = RAMP[i]
        grad.addColorStop(offset, alpha === undefined ? color : rgba(color, alpha))
      }
      return grad
    },
    // A hair of PAPER behind the plot area. The deep end of the ramp is nearly
    // the surface color, so without this lift the tallest marks disappear.
    drawPanel(u) {
      const ctx = u.ctx
      ctx.save()
      ctx.fillStyle = PANEL
      ctx.fillRect(u.bbox.left, u.bbox.top, u.bbox.width, u.bbox.height)
      ctx.restore()
    },
    // Shade the forecast half of the x range so both charts read the same way
    drawForecastRegion(u, kind) {
      if (this.forecastStart === null) {
        return
      }
      const ctx = u.ctx
      const left = u.valToPos(this.forecastStart[kind], 'x', true)
      const right = u.bbox.left + u.bbox.width
      ctx.save()
      ctx.fillStyle = FORECAST_WASH
      ctx.fillRect(left, u.bbox.top, right - left, u.bbox.height)
      ctx.fillStyle = MUTED
      ctx.font = FONT
      ctx.textAlign = 'left'
      ctx.fillText('Predicted', left + 4, u.bbox.top + 12)
      ctx.restore()
    },
    // Threshold annotations: hairline plus a label, so the storm boundary is
    // readable without coloring every bar
    drawKpThresholds(u) {
      const ctx = u.ctx
      ctx.save()
      ctx.font = FONT
      ctx.textAlign = 'right'
      for (const [value, label] of [
        [G1_KP, 'Kp 5 · G1'],
        [G3_KP, 'Kp 7 · G3'],
      ]) {
        if (value > u.scales.y.max) {
          continue
        }
        const y = Math.round(u.valToPos(value, 'y', true)) + 0.5
        ctx.strokeStyle = MUTED
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(u.bbox.left, y)
        ctx.lineTo(u.bbox.left + u.bbox.width, y)
        ctx.stroke()
        ctx.fillStyle = MUTED
        // Flip the label below the line when it would collide with the top edge
        const above = y - 4 > u.bbox.top + 11
        ctx.fillText(label, u.bbox.left + u.bbox.width - 4, above ? y - 4 : y + 12)
      }
      ctx.restore()
    },
  },
}
</script>

<style scoped>
/* Sit directly on the screen background rather than on a card surface. The
   COSMOS tool-base overrides paint v-card-title / v-card-subtitle with the
   surface header color, so clear those too. */
.swx,
.swx :deep(.v-card-title),
.swx :deep(.v-card-subtitle) {
  background: transparent;
}
.swx-logo {
  height: 32px;
  width: auto;
  display: block;
}

/* uPlot ships light-mode defaults; COSMOS themes are all dark */
.swx :deep(.u-title) {
  font: 600 12px system-ui, -apple-system, 'Segoe UI', sans-serif;
  color: rgba(var(--v-theme-on-surface), 0.7);
}
.swx :deep(.u-legend) {
  font: 11px system-ui, -apple-system, 'Segoe UI', sans-serif;
  color: rgba(var(--v-theme-on-surface), 0.7);
}
.swx :deep(.u-legend .u-value) {
  color: rgb(var(--v-theme-on-surface));
  font-variant-numeric: tabular-nums;
}

/* The table sits on the card, so let the card surface show through and put the
   values at full emphasis. Vuetify's default table ink is medium emphasis,
   which is what made these rows hard to read. */
.swx-table {
  background: transparent;
}
/* All rows stay in the table (items-per-page is -1) and the body scrolls, so
   the widget is the same height in either view no matter how many days the
   packet carries. Roughly the height of the two charts it replaces. */
.swx-table :deep(.v-table__wrapper) {
  max-height: 420px;
  overflow-y: auto;
}
/* fixed-header pins the row; it needs an opaque bed or the values scroll
   through it */
.swx-table :deep(th) {
  color: rgba(var(--v-theme-on-surface), 0.7) !important;
  font-weight: 600;
  white-space: nowrap;
  background: rgb(var(--v-theme-surface)) !important;
}
.swx-table :deep(td) {
  color: rgb(var(--v-theme-on-surface)) !important;
  font-variant-numeric: tabular-nums;
}
/* Zebra rows carry the row separation, so the borders can stay hairline */
.swx-table :deep(tbody tr:nth-child(odd) td) {
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.swx-table :deep(tbody tr:hover td) {
  background: rgba(var(--v-theme-on-surface), 0.1);
}
</style>

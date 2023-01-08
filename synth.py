import math
import wave
from array import array

#TODO: Add argparse, with Chords as input
#TODO: Add tempo as parameter
#TODO: Add repeat as parameter
PROGRESSION = ["Cmaj7", "Dm7", "G7", "C6"]

NOTES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']

def transpose(notes, offset):
    return [note + offset for note in notes]

CHORDS = {}

for offset, root in enumerate(NOTES):
    #TODO: Add dim, aug, sus2, sus4, 5
    CHORDS[root] = transpose([36, 48, 52, 55], offset)
    CHORDS[root + 'm'] = transpose([36, 48, 51, 55], offset)
    CHORDS[root + 'm7'] = transpose([36, 48, 51, 55, 58], offset)
    CHORDS[root + '7'] = transpose([24, 43, 46, 48, 52], offset)
    CHORDS[root + 'maj7'] = transpose([36, 48, 52, 55, 59], offset)
    CHORDS[root + '6'] = transpose([36, 48, 52, 57, 64], offset)


class Voice(object):
    def __init__(self, note, length):
        self.note = note
        self.length = length

        self.released = False
        self.t = 0

        self.oscillator = oscillator(self.note)
        self.adsr = ADSREnvelope(0.1, 1.0, 0.7, 3.0)

    def __iter__(self):
        return self

    def __next__(self):
        if self.t >= self.length:
            self.released = True
            self.adsr.trigger_release()
        self.t += 1

        sample = next(self.adsr) * next(self.oscillator)

        # Add filters and other neat effects here, e.g. by feeding the signal
        # to a coroutine.

        return sample

    next = __next__ # For Python2 compatibility

class ADSREnvelope(object):
    """ ADSR envelope generator class """

    RATIO = 1.0 - 1.0 / math.e

    def __init__(self, attack, decay, sustain, release):
        self.attacking = True
        self.released = False
        self.level = 0.0

        compute_coefficient = lambda time: 1.0 - math.exp(-1.0 / (time * 44100.0))

        self.attack = compute_coefficient(attack)
        self.decay = compute_coefficient(decay)
        self.sustain = sustain
        self.release = compute_coefficient(release)

    def __iter__(self):
        return self

    def trigger_release(self):
        self.released = True

    def __next__(self):
        if self.released:
            self.level += self.release * (1.0 - (1.0 / self.RATIO) - self.level)
            if self.level < 0.0:
                # envelope finished
                raise StopIteration
        else:
            if self.attacking:
                self.level += self.attack * ((1.0 / self.RATIO) - self.level)
                if self.level > 1.0:
                    # attack phase finished
                    self.level = 1.0
                    self.attacking = False
            else:
                self.level += self.decay * (self.sustain - self.level)

        return self.level

    next = __next__ # For Python2 compatibility


def oscillator(pitch):
    """ Generate a waveform at a given pitch """
    phi = 0.0
    frequency = (2.0 ** ((pitch - 69.0) / 12.0)) * 440.0
    delta = 2.0 * math.pi * frequency / 44100.0

    while True:
        yield math.sin(phi) + math.sin(2.0 * phi)
        phi += delta

def amplifier(gain, iterable):
    """ Attenuate the input signal by a given gain factor """
    return (gain * sample for sample in iterable)

def chord_generator(iterable):
    """ Converts chord symbols to a list of MIDI notes. """
    return (CHORDS[chord_symbol] for chord_symbol in iterable)

def comp_pattern_generator(iterable):
    """ Converts a list of MIDI notes to (length, notes) tuples in a jazzy pattern. """
    for chord in iterable:
        yield (600, chord)
        yield (300, chord[0:1])
        yield (300, chord)
        yield (600, chord[0:1])
        yield (300, chord)
        yield (300, [chord[0] + 7])

def voice_generator(iterable):
    """ Converts a (length, notes) tuple into a (start time, list of voices) tuple """
    t = 0
    for length, pitches in iterable:
        voices = [Voice(pitch, length) for pitch in pitches]
        yield (t, voices)
        t += length

def voice_combiner(iterable):
    """ Renders samples from voices and maintains a voice pool """
    t = 0.0
    stopping = False
    voice_pool = []
    voice_time, voice_list = next(iterable)

    while True:
        # add new voices to the pool
        while t >= voice_time:
            voice_pool.extend(voice_list)

            try:
                voice_time, voice_list = next(iterable)
            except StopIteration:
                voice_time = float("inf")
                stopping = True

        # pull samples from voices and mix them
        sample = 0.0
        pending_removal = []
        for voice in voice_pool:
            try:
                sample += next(voice)
            except StopIteration:
                # voice has stopped, remove it from the pool
                pending_removal.append(voice)

        # clean up pool
        for voice in pending_removal:
            voice_pool.remove(voice)

        # stop yielding if we're done
        if stopping and len(voice_pool) == 0:
            return

        yield sample
        t += 1000.0 / 44100.0

def quantizer(iterable):
    """ Converts floating point audio signals to 16 bit integers """
    return (int(32767.0 * sample) for sample in iterable)

# create pipeline
chords = chord_generator(PROGRESSION)
comp_pattern = comp_pattern_generator(chords)
voices = voice_generator(comp_pattern)
samples = voice_combiner(voices)
attenuated_samples = amplifier(0.5, samples)
output = quantizer(attenuated_samples)

# prepare audio stream
audiofile = wave.open("output.wav", "wb")
audiofile.setnchannels(1)
audiofile.setsampwidth(2)
audiofile.setframerate(44100)

# render samples
output = list(output)
audiofile.writeframes(array('h', output))
audiofile.writeframes(array('h', output))
audiofile.close()

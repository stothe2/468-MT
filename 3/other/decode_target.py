#!/usr/bin/env python

## This program is built on the decode program written for CS468 MT @ JHU.
## The program implements the beam decoder with target word re-ordering.

import optparse
import sys
import os
from collections import namedtuple
import itertools
baseline_path = os.path.join(os.getcwd()[:-7], "en600.468/decoder/")
if baseline_path not in sys.path:
     sys.path.insert(0, baseline_path)
import models

optparser = optparse.OptionParser()
optparser.add_option("-i", "--input", dest="input", default=baseline_path+"data/input", help="File containing sentences to translate (default=data/input)")
optparser.add_option("-t", "--translation-model", dest="tm", default=baseline_path+"data/tm", help="File containing translation model (default=data/tm)")
optparser.add_option("-l", "--language-model", dest="lm", default=baseline_path+"data/lm", help="File containing ARPA-format language model (default=data/lm)")
optparser.add_option("-n", "--num_sentences", dest="num_sents", default=sys.maxint, type="int", help="Number of sentences to decode (default=no limit)")
optparser.add_option("-k", "--translations-per-phrase", dest="k", default=1, type="int", help="Limit on number of translations to consider per phrase (default=1)")
optparser.add_option("-s", "--stack-size", dest="s", default=1, type="int", help="Maximum stack size (default=1)")
optparser.add_option("-v", "--verbose", dest="verbose", action="store_true", default=False,  help="Verbose mode (default=off)")
opts = optparser.parse_args()[0]

tm = models.TM(opts.tm, opts.k)
lm = models.LM(opts.lm)
french = [tuple(line.strip().split()) for line in open(opts.input).readlines()[:opts.num_sents]]

# tm should translate unknown words as-is with probability 1
for word in set(sum(french,())):
    if (word,) not in tm:
        tm[(word,)] = [models.phrase(word, 0.0)]

def bitmap(sequence):
    """ Generate a coverage bitmap for a sequence of indexes """
    return reduce(lambda x,y: x|y, map(lambda i: long('1'+'0'*i,2), sequence), 0)

def bitmap2str(b, n, on='o', off='.'):
    """ Generate a length-n string representation of bitmap b """
    return '' if n==0 else (on if b&1==1 else off) + bitmap2str(b>>1, n-1, on, off)

def min_index(f, words):
    """ Find minimum index of word in superset f that occurs in subset too """
    i = f.index(words[0])
    for element in words:
        if i > f.index(element):
            i = f.index(element)
    return i

sys.stderr.write("Decoding %s...\n" % (opts.input,))
for f in french:
    # Initialize hypothesis
    hypothesis = namedtuple("hypothesis", "logprob, lm_state, predecessor, phrase")
    initial_hypothesis = hypothesis(0.0, lm.begin(), None, None)
    stacks = [{} for _ in f] + [{}]
    stacks[0][lm.begin()] = initial_hypothesis

    for i, stack in enumerate(stacks[:-1]):
        for h in sorted(stack.itervalues(),key=lambda h: -h.logprob)[:opts.s]: # prune
            for j in xrange(i+1,len(f)+1):
                if f[i:j] in tm:
                    for phrase in tm[f[i:j]]:
                        logprob = h.logprob + phrase.logprob
                        lm_state = h.lm_state
                        ephrase = phrase.english.split()
                        for word in ephrase:
                            (lm_state, word_logprob) = lm.score(lm_state, word)
                            logprob += word_logprob
                        logprob += lm.end(lm_state) if j == len(f) else 0.0
                        new_hypothesis = hypothesis(logprob, lm_state, h, phrase)
                        # Generate hypotheses for swapped target words
                        if len(ephrase) > 1:
                            logprob_swap = h.logprob + phrase.logprob
                            for p in itertools.permutations(ephrase, len(ephrase)):
                                for word in p:
                                    (lm_state, word_logprob) = lm.score(lm_state, word)
                                    logprob_swap += word_logprob
                                logprob_swap += lm.end(lm_state) if j == len(f) else 0.0
                                if logprob_swap > logprob:
                                    phrase._replace(english = " ".join(p))
                                    new_hypothesis = hypothesis(logprob_swap, lm_state, h, phrase)

                        if lm_state not in stacks[j] or stacks[j][lm_state].logprob < logprob: # second case is recombination
                            stacks[j][lm_state] = new_hypothesis

    winner = max(stacks[-1].itervalues(), key=lambda h: h.logprob)
    def extract_english(h):
        return "" if h.predecessor is None else "%s%s " % (extract_english(h.predecessor), h.phrase.english)
    print extract_english(winner)

#ifndef SEQUENCE_H
#define SEQUENCE_H

#include <string>
#include <vector>
#include <fstream>
#include <stdexcept>
#include <cctype>

struct FastaSequence {
    std::string name;
    std::string sequence;
    std::vector<int> encoded;
};

class FastaParser {
public:
    static std::vector<FastaSequence> parse(const std::string& filename) {
        std::ifstream file(filename);
        if (!file.is_open()) {
            throw std::runtime_error("Cannot open file: " + filename);
        }

        std::vector<FastaSequence> sequences;
        std::string line;
        FastaSequence current;
        bool in_sequence = false;

        while (std::getline(file, line)) {
            if (line.empty()) continue;
            
            if (line[0] == '>') {
                if (in_sequence) {
                    encode_sequence(current);
                    sequences.push_back(current);
                }
                current.name = line.substr(1);
                current.sequence.clear();
                current.encoded.clear();
                in_sequence = true;
            } else if (in_sequence) {
                for (char c : line) {
                    if (std::isalpha(c)) {
                        current.sequence += std::toupper(c);
                    }
                }
            }
        }

        if (in_sequence) {
            encode_sequence(current);
            sequences.push_back(current);
        }

        file.close();
        return sequences;
    }

    static int char_to_code(char c) {
        switch (c) {
            case 'A': case 'a': return 0;
            case 'C': case 'c': return 1;
            case 'G': case 'g': return 2;
            case 'T': case 't': return 3;
            default: return -1;
        }
    }

    static char code_to_char(int code) {
        switch (code) {
            case 0: return 'A';
            case 1: return 'C';
            case 2: return 'G';
            case 3: return 'T';
            default: return 'N';
        }
    }

    static std::string code_to_string(const std::vector<int>& codes) {
        std::string s;
        for (int c : codes) s += code_to_char(c);
        return s;
    }

private:
    static void encode_sequence(FastaSequence& seq) {
        seq.encoded.reserve(seq.sequence.size());
        for (char c : seq.sequence) {
            seq.encoded.push_back(char_to_code(c));
        }
    }
};

#endif

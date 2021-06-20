from abc import ABC, abstractmethod
import math
from optparse import OptionParser
import os
import queue
import random as rand
import sys


class Generator(ABC):

    def __init__(self, card, geo, dim, dist, output, output_format):
        self.card = card
        self.geo = geo
        self.dim = dim
        self.dist = dist
        self.output = output
        self.output_format = output_format

    def bernoulli(self, p):
        return 1 if rand.random() < p else 0

    def normal(self, mu, sigma):
        return mu + sigma * math.sqrt(-2 * math.log(rand.random())) * math.sin(2 * math.pi * rand.random())

    def is_valid_point(self, point):
        for x in point.coordinates:
            if not (0 <= x <= 1):
                return False
        return True

    @abstractmethod
    def generate(self):
        pass


class PointGenerator(Generator):

    def __init__(self, card, geo, dim, dist, output, output_format):
        super(PointGenerator, self).__init__(card, geo, dim, dist, output, output_format)

    def generate(self):
        geometries = []
        prev_point = None

        i = 0
        while i < self.card:
            point = self.generate_point(i, prev_point)

            if self.is_valid_point(point):
                prev_point = point
                geometries.append(prev_point)
                i = i + 1

        return geometries

    def generate_and_write(self):

        output_filename = '{0}.{1}'.format(self.output, self.output_format)
        f = open(output_filename, 'w', encoding='utf8')

        prev_point = None

        i = 0
        while i < self.card:
            point = self.generate_point(i, prev_point)

            if self.is_valid_point(point):
                prev_point = point
                f.writelines('{0}\n'.format(prev_point.to_string(self.output_format)))
                i = i + 1

        f.close()

    @abstractmethod
    def generate_point(self, i, prev_point):
        pass


class UniformGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output, output_format):
        super(UniformGenerator, self).__init__(card, geo, dim, dist, output, output_format)

    def generate_point(self, i, prev_point):
        coordinates = [rand.random() for d in range(self.dim)]
        return Point(coordinates)


class DiagonalGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output, output_format, percentage, buffer):
        super(DiagonalGenerator, self).__init__(card, geo, dim, dist, output, output_format)
        self.percentage = percentage
        self.buffer = buffer

    def generate_point(self, i, prev_point):
        if self.bernoulli(self.percentage) == 1:
            coordinates = [rand.random()] * self.dim
        else:
            c = rand.random()
            d = self.normal(0, self.buffer / 5)

            coordinates = [(c + (1 - 2 * (x % 2)) * d / math.sqrt(2)) for x in range(self.dim)]
        return Point(coordinates)


class GaussianGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output, output_format):
        super(GaussianGenerator, self).__init__(card, geo, dim, dist, output, output_format)

    def generate_point(self, i, prev_point):
        coordinates = [self.normal(0.5, 0.1) for d in range(self.dim)]
        return Point(coordinates)


class SierpinskiGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output, output_format):
        super(SierpinskiGenerator, self).__init__(card, geo, dim, dist, output, output_format)

    def generate_point(self, i, prev_point):
        if i == 0:
            return Point([0.0, 0.0])
        elif i == 1:
            return Point([1.0, 0.0])
        elif i == 2:
            return Point([0.5, math.sqrt(3) / 2])
        else:
            d = self.dice(5)

            if d == 1 or d == 2:
                return self.get_middle_point(prev_point, Point([0.0, 0.0]))
            elif d == 3 or d == 4:
                return self.get_middle_point(prev_point, Point([1.0, 0.0]))
            else:
                return self.get_middle_point(prev_point, Point([0.5, math.sqrt(3) / 2]))

    def dice(self, n):
        return math.floor(rand.random() * n) + 1

    def get_middle_point(self, point1, point2):
        middle_point_coords = []
        for i in range(len(point1.coordinates)):
            middle_point_coords.append((point1.coordinates[i] + point2.coordinates[i]) / 2)
        return Point(middle_point_coords)


class BitGenerator(PointGenerator):

    def __init__(self, card, geo, dim, dist, output, output_format, prob, digits):
        super(BitGenerator, self).__init__(card, geo, dim, dist, output, output_format)
        self.prob = prob
        self.digits = digits

    def generate_point(self, i, prev_point):
        coordinates = [self.bit() for d in range(self.dim)]
        return Point(coordinates)

    def bit(self):
        num = 0.0
        for i in range(1, self.digits + 1):
            c = self.bernoulli(self.prob)
            num = num + c / (math.pow(2, i))
        return num


class ParcelGenerator(Generator):

    def __init__(self, card, geo, dim, dist, output, output_format, split_range, dither):
        super(ParcelGenerator, self).__init__(card, geo, dim, dist, output, output_format)
        self.split_range = split_range
        self.dither = dither

    def generate(self):
        geometries = []
        box = Box(0.0, 0.0, 1.0, 1.0)
        boxes = queue.Queue(self.card)
        boxes.put(box)

        while boxes.qsize() < self.card:
            # Dequeue the queue to get a box
            b = boxes.get()

            if b.w > b.h:
                # Split vertically if width is bigger than height
                split_size = b.w * rand.uniform(self.split_range, 1 - self.split_range)
                b1 = Box(b.x, b.y, split_size, b.h)
                b2 = Box(b.x + split_size, b.y, b.w - split_size, b.h)
            else:
                # Split horizontally if width is less than height
                split_size = b.h * rand.uniform(self.split_range, 1 - self.split_range)
                b1 = Box(b.x, b.y, b.w, split_size)
                b2 = Box(b.x, b.y + split_size, b.w, b.h - split_size)

            boxes.put(b1)
            boxes.put(b2)

        while not boxes.empty():
            b = boxes.get()
            b.w = b.w * (1.0 - rand.uniform(0.0, self.dither))
            b.h = b.h * (1.0 - rand.uniform(0.0, self.dither))
            geometries.append(b)

        return geometries


class Geometry(ABC):

    def to_string(self, output_format):
        if output_format == 'csv':
            return self.to_csv_string()
        elif output_format == 'wkt':
            return self.to_wkt_string()
        else:
            print('Please check the output format.')
            sys.exit()

    @abstractmethod
    def to_csv_string(self):
        pass

    @abstractmethod
    def to_wkt_string(self):
        pass


class Point(Geometry):

    def __init__(self, coordinates):
        self.coordinates = coordinates

    def to_csv_string(self):
        return ','.join(str(x) for x in self.coordinates)

    def to_wkt_string(self):
        return 'POINT ({0})'.format(' '.join(str(x) for x in self.coordinates))


class Box(Geometry):

    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def to_csv_string(self):
        return '{},{},{},{}'.format(self.x, self.y, self.x + self.w, self.y + self.h)

    def to_wkt_string(self):
        x1, y1, x2, y2 = self.x, self.y, self.x + self.w, self.y + self.h
        return 'POLYGON (({} {}, {} {}, {} {}, {} {}, {} {}))'.format(x1, y1, x2, y1, x2, y2, x1, y2, x1, y1)


def main():
    """
    Generate a list of geometries and write the list to file
    :return:
    """

    parser = OptionParser()
    parser.add_option('-c', '--card', type='int', help='The number of records to generate.')
    parser.add_option('-g', '--geo', type='string',
                      help='Geometry type. Currently the generator supports {point, rectangle}.')
    parser.add_option('-d', '--dim', type='int',
                      help='The dimensionality of the generated geometries. Currently, on two-dimensional data is supported.')
    parser.add_option('-t', '--dist', type='string',
                      help='The available distributions are: {uniform, diagonal, gaussian, sierpinsk, bit, parcel}.')
    parser.add_option('-p', '--percentage', type='float',
                      help='Diagonal distribution: The percentage (ratio) of the points that are exactly on the line.')
    parser.add_option('-b', '--buffer', type='float',
                      help='Diagonal distribution: The size of the buffer around the line where additional geometries are scattered.')
    parser.add_option('-o', '--output', type='string', help='Path to the output file')
    parser.add_option('-q', '--prob', type='float',
                      help='Bit distribution: The probability of setting each bit independently to 1.')
    parser.add_option('-n', '--digits', type='int',
                      help='Bit distribution: The number of binary digits after the fraction point.')
    parser.add_option('-r', '--split_range', type='float',
                      help='Parcel distribution: The minimum tiling range for splitting a box. r = 0 indicates that all the ranges are allowed while r = 0.5 indicates that a box is always split into half.')
    parser.add_option('-e', '--dither', type='float',
                      help='Parcel distribution: The dithering parameter that adds some random noise to the generated rectangles. d = 0 indicates no dithering and d = 1.0 indicates maximum dithering that can shrink rectangles down to a single point.')
    parser.add_option('-f', '--format', type='string',
                      help='Output format. Currently the generator supports {csv, wkt}')

    (options, args) = parser.parse_args()
    options_dict = vars(options)
    print(options_dict)
    try:
        card, geo, dim, dist, output, output_format = options_dict['card'], options_dict['geo'], options_dict['dim'], \
                                                      options_dict['dist'], options_dict['output'], options_dict[
                                                          'format']
    except RuntimeError:
        print('Please check your arguments')

    if dist == 'uniform':
        generator = UniformGenerator(card, geo, dim, dist, output, output_format)

    elif dist == 'diagonal':
        percentage, buffer = options_dict['percentage'], options_dict['buffer']
        generator = DiagonalGenerator(card, geo, dim, dist, output, output_format, percentage, buffer)

    elif dist == 'gaussian':
        generator = GaussianGenerator(card, geo, dim, dist, output, output_format)

    elif dist == 'sierpinski':
        if dim != 2:
            print('Currently we only support 2 dimensions for Sierpinski distribution')
            sys.exit()

        generator = SierpinskiGenerator(card, geo, dim, dist, output, output_format)

    elif dist == 'bit':
        prob, digits = options_dict['prob'], options_dict['digits']
        generator = BitGenerator(card, geo, dim, dist, output, output_format, prob, digits)

    elif dist == 'parcel':
        if dim != 2:
            print('Currently we only support 2 dimensions for Parcel distribution')
            sys.exit()

        split_range, dither = options_dict['split_range'], options_dict['dither']
        generator = ParcelGenerator(card, geo, dim, dist, output, output_format, split_range, dither)

    else:
        print('Please check the distribution type.')
        sys.exit()

    generator.generate_and_write()

    # geometries = generator.generate()
    #
    # if not os.path.exists('output'):
    #     os.mkdir('output')
    #
    # output_filename = 'output/{0}.{1}'.format(output, output_format)
    # f = open(output_filename, 'w', encoding='utf8')
    #
    # for g in geometries:
    #     f.writelines('{0}\n'.format(g.to_string(output_format)))

    # f.close()


if __name__ == "__main__":
    main()
